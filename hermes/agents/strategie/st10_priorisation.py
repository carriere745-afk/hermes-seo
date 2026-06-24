"""ST10 — Priorisation Globale.

Applique une matrice de priorisation configurable a toutes les recommandations.
Re-evalue les priorites en fonction de la configuration client.
Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st10")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st10"
    state.phase = "synthese"

    config = state.priorisation_config
    poids_business = config.get("poids_business", 0.35)
    poids_faisabilite = config.get("poids_faisabilite", 0.20)
    poids_effort = config.get("poids_effort", 0.15)
    poids_volume = config.get("poids_volume", 0.15)
    poids_opportunite = config.get("poids_opportunite", 0.10)
    poids_urgence = config.get("poids_urgence", 0.05)

    for rec in state.recommandations:
        if rec.priorite == "KILL":
            continue

        # Scores normalises 0-100
        business_score = state.business_scores.get(rec.sujet, 50.0)
        feasibility = float(state.feasibility_scores.get(rec.sujet, 50))
        # Effort inverse (moins d'effort = meilleur score)
        effort_h = _parse_effort_hours(rec.effort_estime)
        effort_score = max(0, 100 - (effort_h * 10))
        # Volume normalise
        volume_score = min(100, rec.volume_recherche / 50)
        # Opportunite
        opp_score = _find_opportunite_score(rec.sujet, state.opportunites)
        # Urgence (cannibalisations critiques = urgent)
        urgence_score = _compute_urgence(rec, state)

        # Score pondere final
        final_score = (
            poids_business * business_score +
            poids_faisabilite * feasibility +
            poids_effort * effort_score +
            poids_volume * volume_score +
            poids_opportunite * opp_score +
            poids_urgence * urgence_score
        )

        # Re-prioriser
        if final_score >= 75:
            rec.priorite = "P0"
        elif final_score >= 55:
            rec.priorite = "P1"
        elif final_score >= 30:
            rec.priorite = "P2"
        else:
            rec.priorite = "P3"

    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st10", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    p0p1 = sum(1 for r in state.recommandations if r.priorite in ("P0", "P1"))
    logger.info(f"ST10: Priorisation finale — {p0p1} recommandations P0/P1")
    return state


def _parse_effort_hours(effort_str: str) -> float:
    try:
        if "h" in effort_str:
            return float(effort_str.replace("h", "").strip().split("-")[0])
        return 4.0
    except (ValueError, AttributeError):
        return 4.0


def _find_opportunite_score(sujet: str, opportunites: list[dict]) -> float:
    for opp in opportunites:
        if opp.get("sujet") == sujet:
            return float(opp.get("opportunite_score", 50))
    return 50.0


def _compute_urgence(rec, state: StrategieState) -> float:
    score = 50.0
    for cannib in state.cannibalisations:
        if cannib.get("keyword", "") in rec.keywords:
            if cannib.get("gravite") == "critical":
                score = 100.0
            elif cannib.get("gravite") == "high":
                score = 80.0
    # Flags YMYL
    for flag in state.revue_humaine_flags:
        if flag.get("sujet") == rec.sujet:
            if flag.get("review_priority") == "high":
                score = max(score, 90.0)
    return score
