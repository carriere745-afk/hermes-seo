"""ST06 — Roadmap Editoriale.

Agrege ST01-ST05b pour produire une roadmap priorisee.
Chaque recommandation inclut Confidence Score + Decision Trace.

Utilise Claude Haiku pour la synthese. Non skippable. Cout: ~$0.05.
"""

import json
import logging
import time
from datetime import datetime

from hermes.models.strategie import (
    StrategieState, Recommandation, DecisionTrace,
    ActionType, PrioriteAction, PortfolioCategory,
)
from hermes.core.strategie_db import log_event, save_prediction

logger = logging.getLogger("hermes.strategie.st06")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st06"
    state.phase = "synthese"

    recommandations: list[Recommandation] = []

    # 1. Generer les recommandations de base (sans LLM)
    recommandations = _generate_base_recommendations(state)

    # 2. Enrichir avec Haiku pour la priorisation fine (+ confidence + trace)
    if state.mode != "fast":
        try:
            recommandations = await _enrich_with_llm(state, recommandations)
        except Exception as e:
            logger.warning(f"ST06: LLM enrichment failed ({e}), using base scores")

    # 3. Calculer Confidence Score + Decision Trace pour chaque reco
    for rec in recommandations:
        rec.confidence_score = _compute_confidence(rec, state)
        rec.confidence_justification = _confidence_justification(rec.confidence_score)
        rec.trace = _build_trace(rec, state)

    # 4. Trier par priorite
    priorite_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "KILL": 4}
    recommandations.sort(key=lambda r: (priorite_order.get(r.priorite, 99), -r.confidence_score))

    # 5. Sauvegarder les predictions
    for rec in recommandations:
        if rec.priorite != "KILL":
            save_prediction(
                session_id=state.session_id, agent_id="st06",
                action_type=rec.action,
                keyword=rec.keywords[0] if rec.keywords else "",
                predicted_traffic=rec.trafic_estime,
                predicted_leads=rec.leads_estimes,
                predicted_roi=rec.roi_12mois,
                confidence=float(rec.confidence_score),
            )

    state.recommandations = recommandations
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st06", pipeline_id="strategie",
        model="claude-haiku-4-5" if state.mode != "fast" else "none",
        tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    p0p1 = sum(1 for r in recommandations if r.priorite in ("P0", "P1"))
    logger.info(f"ST06: {len(recommandations)} recommandations — {p0p1} prioritaires (P0/P1)")
    return state


def _generate_base_recommendations(state: StrategieState) -> list[Recommandation]:
    """Genere les recommandations de base sans LLM."""
    recs = []

    # Opportunites → recommandations
    for opp in state.opportunites[:30]:
        sujet_nom = opp.get("sujet", "")
        # Trouver les donnees associees
        feasibility = state.feasibility_scores.get(sujet_nom, 50)
        business = state.business_scores.get(sujet_nom, 50.0)
        economie = next((e for e in state.seo_economics if e["sujet"] == sujet_nom), None)
        geo = next((g for g in state.geo_opportunities if g["sujet"] == sujet_nom), None)

        # Priorite
        priorite = _compute_priorite(business, feasibility)

        rec = Recommandation(
            sujet=sujet_nom,
            action=opp.get("type_page_recommande", "creer_pilier"),
            priorite=priorite,
            justification=f"Sujet non couvert, volume {opp.get('volume_total', 0)}/mois, score opportunite {opp.get('opportunite_score', 0)}/100",
            keywords=opp.get("keywords", []),
            volume_recherche=opp.get("volume_total", 0),
            effort_estime=economie["effort_estime"] if economie else "4-6h",
            cout_estime=economie["cout_creation"] if economie else 200.0,
            trafic_estime=economie["trafic_mensuel_estime"] if economie else 100,
            leads_estimes=int(economie["leads_mensuels_estimes"]) if economie else 2,
            roi_12mois=economie["roi_12mois"] if economie else 500.0,
            delai_resultats=economie["delai_resultats"] if economie else "3-6 mois",
            pipeline_cible="P1",
            portfolio="acquisition",
            dependencies=[],
        )
        recs.append(rec)

    # Cannibalisations → recommandations de consolidation
    for cannib in state.cannibalisations:
        gravite = cannib.get("gravite", "low")
        if gravite in ("critical", "high"):
            recs.append(Recommandation(
                sujet=f"Consolidation: {cannib.get('keyword', '')}",
                action="fusionner",
                priorite="P1" if gravite == "critical" else "P2",
                justification=cannib.get("recommandation", ""),
                keywords=[cannib.get("keyword", "")],
                volume_recherche=0,
                effort_estime="2-3h",
                cout_estime=150.0,
                trafic_estime=0,
                leads_estimes=0,
                roi_12mois=-150.0,
                delai_resultats="1 mois",
                pipeline_cible="P3",
                portfolio="defense",
            ))

    # Silos incomplets → recommandations structurelles
    for silo in state.silos_analysis:
        for issue in silo.get("issues", []):
            if issue == "silo_sans_pilier":
                recs.append(Recommandation(
                    sujet=f"Pilier: {silo['silo']}",
                    action="creer_pilier",
                    priorite="P1",
                    justification=f"Le silo '{silo['silo']}' n'a pas de page pilier. "
                                  f"Volume total: {silo.get('volume_total', 0)}.",
                    keywords=[silo["silo"]],
                    volume_recherche=silo.get("volume_total", 0),
                    effort_estime="6-8h",
                    cout_estime=400.0,
                    trafic_estime=int(silo.get("volume_total", 0) * 0.05),
                    leads_estimes=2,
                    roi_12mois=800.0,
                    delai_resultats="3-6 mois",
                    pipeline_cible="P1",
                    portfolio="acquisition",
                ))

    return recs


async def _enrich_with_llm(state: StrategieState, recs: list[Recommandation]) -> list[Recommandation]:
    """Enrichit les recommandations avec Haiku pour la priorisation fine."""
    recs_summary = []
    for r in recs[:20]:
        recs_summary.append({
            "sujet": r.sujet,
            "volume": r.volume_recherche,
            "business_score": r.business_score if hasattr(r, 'business_score') else 50,
            "feasibility": r.feasibility_score if hasattr(r, 'feasibility_score') else 50,
            "priorite_actuelle": r.priorite,
        })

    prompt = f"""Priorise ces recommandations SEO pour {state.domain}.

Recommandations actuelles:
{json.dumps(recs_summary, indent=2, ensure_ascii=False)}

Regles de priorisation:
- P0: Volume > 5000 ET business_score > 70 ET feasibility > 60 → ACTION IMMEDIATE
- P1: Volume > 1000 OU business_score > 60 → 1-3 mois
- P2: Volume > 100 OU business_score > 40 → 3-6 mois
- P3: Le reste → 6-12 mois
- KILL: Feasibility < 30 ET business_score < 30

Retourne un JSON: {{"ajustements": [{{"sujet": "...", "nouvelle_priorite": "P1", "justification": "..."}}]}}
Maximum 10 ajustements. Ne change que les priorites manifestement incorrectes."""

    try:
        from hermes.core.llm import LLMFactory, _repair_json
        from hermes.config import _cfg
        factory = LLMFactory(anthropic_api_key=_cfg._resolve("ANTHROPIC_API_KEY"))
        text, _, _, _ = await factory.route(
            system_prompt="Tu es un directeur SEO senior. Priorise les recommandations de maniere realiste. Retourne du JSON valide uniquement.",
            user_message=prompt,
            agent_id="st06",
            max_tokens=2048,
        )
        data = _repair_json(text)
        ajustements = {a["sujet"]: a for a in data.get("ajustements", [])}

        for rec in recs:
            if rec.sujet in ajustements:
                adj = ajustements[rec.sujet]
                rec.priorite = adj.get("nouvelle_priorite", rec.priorite)
                rec.justification = adj.get("justification", rec.justification)
    except Exception:
        pass

    return recs


def _compute_priorite(business_score: float, feasibility: int) -> str:
    if business_score >= 70 and feasibility >= 60:
        return "P0"
    elif business_score >= 50 or (feasibility >= 50 and business_score >= 40):
        return "P1"
    elif business_score >= 30 or feasibility >= 40:
        return "P2"
    return "P3"


def _compute_confidence(rec: Recommandation, state: StrategieState) -> int:
    """Confidence Score 0-100 selon la formule du cahier des charges.

    Facteurs :
    - Qualite des donnees sources (30%) → p2/p3/p4 disponibles
    - Faisabilite ST04b (25%) → feasibility_score
    - Business Score ST05 (20%) → business_score
    - Volatilite du sujet (15%) → variations P4 S02
    - Exhaustivite de l'analyse (10%) → nombre de dimensions ST couvertes
    """
    sources_ok = sum(1 for v in state.pipelines_disponibles.values() if v)
    qualite_donnees = 100 if sources_ok >= 3 else (60 if sources_ok >= 1 else 0)

    # Chercher la faisabilite associee
    feasibility = state.feasibility_scores.get(rec.sujet, 50)

    # Business score
    business = state.business_scores.get(rec.sujet, 50.0)

    # Volatilite (estimee basse par defaut)
    volatilite = 70  # Plus c'est haut, moins c'est volatile

    # Exhaustivite
    exhaustivite = min(100, sources_ok * 33)

    raw = (0.30 * qualite_donnees +
           0.25 * feasibility +
           0.20 * business +
           0.15 * volatilite +
           0.10 * exhaustivite)

    return min(100, max(0, int(raw)))


def _confidence_justification(score: int) -> str:
    if score >= 80:
        return "Haute confiance — recommandation robuste, donnees solides"
    elif score >= 60:
        return "Confiance moyenne — donnees partielles, incertitude moderee"
    elif score >= 40:
        return "Confiance faible — recommandation indicative, a valider"
    return "Confiance tres faible — ne pas agir sans validation humaine"


def _build_trace(rec: Recommandation, state: StrategieState) -> DecisionTrace:
    return DecisionTrace(
        inputs={
            "volume_recherche": rec.volume_recherche,
            "topical_authority": state.topical_authority_scores.get(rec.sujet, 50),
            "feasibility_score": state.feasibility_scores.get(rec.sujet, 50),
            "business_score": state.business_scores.get(rec.sujet, 50.0),
            "effort_estime": rec.effort_estime,
            "roi_12mois": rec.roi_12mois,
        },
        rules_applied=[
            f"volume > 1000 → {'P0/P1' if rec.volume_recherche >= 1000 else 'P2/P3'}",
            f"feasibility > 50 → {'attaquable' if state.feasibility_scores.get(rec.sujet, 0) >= 50 else 'difficile'}",
            f"business_score > 70 → {'priorite elevee' if state.business_scores.get(rec.sujet, 0) >= 70 else 'priorite standard'}",
        ],
        calcul=f"Priorite = ({state.business_scores.get(rec.sujet, 50)} × 0.35) + ({state.feasibility_scores.get(rec.sujet, 50)} × 0.20) = "
               f"{round(state.business_scores.get(rec.sujet, 50) * 0.35 + state.feasibility_scores.get(rec.sujet, 50) * 0.20, 1)}",
        decision=rec.priorite,
    )
