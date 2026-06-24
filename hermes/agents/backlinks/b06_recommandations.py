"""B06 — Recommandations & Plan d'Action.

Agrege B02-B14 pour produire un plan d'action priorise.
Chaque recommandation inclut : type, cout estime, impact, delai, priorite.
Utilise Claude Haiku pour la synthese. Non skippable. Cout: ~$0.05.
"""

import json
import logging
import time
from datetime import datetime

from hermes.models.backlinks import (
    BacklinksState, BacklinkRecommandation,
)
from hermes.core.backlinks_db import insert_opportunities_batch
from hermes.core.strategie_db import log_event, save_prediction

logger = logging.getLogger("hermes.backlinks.b06")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b06"
    state.phase = "synthese"

    recommandations: list[BacklinkRecommandation] = []

    # 1. Opportunites des gaps concurrentiels → recommandations
    for gap in state.competitor_gaps[:15]:
        recommandations.append(BacklinkRecommandation(
            domaine_cible=gap.get("domain", ""),
            type_action="guest_post",
            priorite="P1" if gap.get("score_gap", 0) >= 70 else "P2",
            justification=f"Domaine linkant {gap.get('concurrent', 'un concurrent')} mais pas vous. DR: {gap.get('domain_rating', 0)}",
            cout_estime=150.0 if gap.get("domain_rating", 0) > 60 else 80.0,
            effort_estime="2-3h",
            impact_estime=f"+{gap.get('score_gap', 0)} points d'autorite estimes",
            delai_estime="2-4 semaines",
            confidence_score=int(gap.get("score_gap", 50) * 0.8),
        ))

    # 2. Prospects → recommandations
    for disc in state.prospect_discoveries[:10]:
        recommandations.append(BacklinkRecommandation(
            domaine_cible=disc.get("domain", ""),
            type_action=disc.get("opportunity_type", "guest_post"),
            priorite="P1" if disc.get("relevance_score", 0) >= 70 else "P2",
            justification=f"Prospect {disc.get('domain_type', '')} pertinent — DR {disc.get('domain_rating', 0)}, Topical {disc.get('topical_score', 0)}",
            cout_estime=150.0 if disc.get("domain_rating", 0) > 60 else 80.0,
            effort_estime="1-2h",
            impact_estime=f"Score de pertinence: {disc.get('relevance_score', 0)}/100",
            confidence_score=int(disc.get("relevance_score", 50) * 0.85),
        ))

    # 3. Reclamations → recommandations
    for rec in state.link_reclamations[:10]:
        recommandations.append(BacklinkRecommandation(
            domaine_cible=rec.get("source_domain", ""),
            type_action="broken_link" if rec.get("type") == "lost_link" else "mention",
            priorite="P1",
            justification=rec.get("raison", ""),
            cout_estime=0.0,
            effort_estime="30min",
            impact_estime="Recuperation de lien/mention existant",
            confidence_score=80,
        ))

    # 4. Anchor strategy → recommandations structurelles
    alerts = state.anchor_profile.get("alerts", [])
    for alert in alerts[:5]:
        recommandations.append(BacklinkRecommandation(
            domaine_cible="",
            type_action="anchor_adjustment",
            priorite="P2",
            justification=alert,
            cout_estime=0.0,
            effort_estime="Continu",
            impact_estime="Maintien du profil d'ancres naturel",
            confidence_score=70,
        ))

    # 5. Enrichir avec Haiku si disponible
    if state.mode != "fast":
        try:
            recommandations = await _enrich_with_llm(state, recommandations)
        except Exception as e:
            logger.warning(f"B06: LLM enrichment failed: {e}")

    # 6. Prioriser (P0 → P3)
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    recommandations.sort(key=lambda r: (priority_order.get(r.priorite, 99), -r.confidence_score))

    # 7. Sauvegarder les predictions
    for rec in recommandations[:20]:
        if rec.priorite != "P3":
            save_prediction(
                session_id=state.session_id, agent_id="b06",
                pipeline_id="backlinks",
                action_type=rec.type_action,
                url=rec.domaine_cible,
                predicted_roi=rec.cout_estime * -1,  # Cout = investissement
            )

    state.recommandations = recommandations
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="b06", pipeline_id="backlinks",
        model="claude-haiku-4-5" if state.mode != "fast" else "none",
        tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
    )

    p0p1 = sum(1 for r in recommandations if r.priorite in ("P0", "P1"))
    logger.info(f"B06: {len(recommandations)} recommandations — {p0p1} prioritaires (P0/P1)")
    return state


async def _enrich_with_llm(state: BacklinksState, recs: list[BacklinkRecommandation]) -> list[BacklinkRecommandation]:
    recs_summary = [{
        "domaine": r.domaine_cible, "type": r.type_action,
        "priorite": r.priorite, "cout": r.cout_estime,
        "justification": r.justification[:100],
    } for r in recs[:15]]

    prompt = f"""Priorise ces recommandations de netlinking pour {state.domain}.

Recommandations actuelles:
{json.dumps(recs_summary, indent=2, ensure_ascii=False)}

Regles:
- P0: Cout 0 (reclamation) ET impact eleve
- P1: DR > 60 OU opportunite concurrente
- P2: DR 40-60 OU prospect pertinent
- P3: Le reste

Retourne un JSON: {{"ajustements": [{{"domaine": "...", "nouvelle_priorite": "P1", "justification": "..."}}]}}
Maximum 10 ajustements."""

    try:
        from hermes.core.llm import LLMFactory, _repair_json
        from hermes.config import _cfg
        factory = LLMFactory(anthropic_api_key=_cfg._resolve("ANTHROPIC_API_KEY"))
        text, _, _, _ = await factory.route(
            system_prompt="Tu es un expert en netlinking et SEO off-site. Priorise les recommandations. JSON uniquement.",
            user_message=prompt, agent_id="b06", max_tokens=2048,
        )
        data = _repair_json(text)
        ajustements = {a["domaine"]: a for a in data.get("ajustements", [])}
        for rec in recs:
            if rec.domaine_cible in ajustements:
                adj = ajustements[rec.domaine_cible]
                rec.priorite = adj.get("nouvelle_priorite", rec.priorite)
                rec.justification = adj.get("justification", rec.justification)
    except Exception:
        pass
    return recs
