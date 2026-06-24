"""ST10b — Kill List.

Identifie les sujets a ne SURTOUT PAS traiter :
- Cannibalisations severes
- Hors scope secteur
- Faible potentiel avec cout eleve
- YMYL sans expertise
- Duplicats / pages mortes

Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState, KillListEntry, DecisionTrace
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st10b")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st10b"
    state.phase = "synthese"

    kill_list: list[KillListEntry] = []

    # 1. Recommandations deja marquees KILL
    for rec in state.recommandations:
        if rec.priorite == "KILL":
            kill_list.append(KillListEntry(
                sujet=rec.sujet,
                raison="Priorite KILL de ST06",
                categorie="faible_potentiel",
                severite="medium",
                keywords=rec.keywords,
                justification=rec.justification,
                trace=rec.trace,
            ))

    # 2. Cannibalisations critiques → fusion plutot que creation
    for cannib in state.cannibalisations:
        if cannib.get("gravite") == "critical":
            kw = cannib.get("keyword", "")
            if not any(k.sujet == kw for k in kill_list):
                kill_list.append(KillListEntry(
                    sujet=f"Cannibalisation: {kw}",
                    raison="Cannibalisation critique — ne pas creer de nouvelle page",
                    categorie="cannibalisation",
                    severite="critical",
                    keywords=[kw],
                    page_concernee=", ".join(cannib.get("pages_concernees", [])),
                    justification="Pages multiples en competition sur le meme mot-cle. "
                                  "Creer une nouvelle page aggraverait la situation. Fusionner les pages existantes.",
                    trace=DecisionTrace(
                        inputs={"gravite": "critical", "n_pages": cannib.get("n_pages", 2)},
                        rules_applied=["cannibalisation critique → ne pas creer"],
                        calcul="gravite critique + n_pages >= 2 → KILL",
                        decision="KILL — Fusion recommandee",
                    ),
                ))

    # 3. Sujets avec business score tres faible + cout eleve
    for eco in state.seo_economics:
        if eco.get("business_score", 0) < 20 and eco.get("cout_creation", 0) > 300:
            sujet = eco["sujet"]
            if not any(k.sujet == sujet for k in kill_list):
                kill_list.append(KillListEntry(
                    sujet=sujet,
                    raison=f"Faible potentiel (business={eco['business_score']}) avec cout eleve ({eco['cout_creation']} euros)",
                    categorie="faible_potentiel",
                    severite="medium",
                    keywords=[],
                    justification=f"ROI estime negatif ou insignifiant. Cout de creation superieur au benefice attendu.",
                    trace=DecisionTrace(
                        inputs={"business_score": eco["business_score"], "cout": eco["cout_creation"]},
                        rules_applied=["business_score < 20 ET cout > 300 → KILL"],
                        calcul=f"business={eco['business_score']} < 20, cout={eco['cout_creation']} > 300 → KILL",
                        decision="KILL — Non rentable",
                    ),
                ))

    # 4. YMYL flags de ST09
    for flag in state.revue_humaine_flags:
        if flag.get("ymyl") and flag.get("review_priority") == "high":
            sujet = flag["sujet"]
            if not any(k.sujet == sujet for k in kill_list):
                kill_list.append(KillListEntry(
                    sujet=sujet,
                    raison=f"YMYL — necessite expertise metier ({', '.join(flag.get('ymyl_patterns', []))})",
                    categorie="ymyl",
                    severite="critical" if flag.get("controverse") else "high",
                    keywords=flag.get("keywords", []),
                    justification="Sujet sensible (YMYL). Ne pas traiter sans expert valide dans le domaine. "
                                  "Risque legal et reputationnel eleve.",
                ))

    state.kill_list = kill_list
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st10b", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST10b: {len(kill_list)} sujets en Kill List")
    return state
