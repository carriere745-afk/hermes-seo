"""ST05 — Business Score.

Calcule un score business 0-100 pour chaque sujet :
trafic estime × taux de conversion × valeur lead.

Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st05")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st05"
    state.phase = "analyse"

    business_scores: dict[str, float] = {}
    taux_conversion = state.taux_conversion
    valeur_lead = state.valeur_lead

    for sujet in state.sujets:
        volume = sujet.volume_total
        position = sujet.position_moyenne if hasattr(sujet, 'position_moyenne') else 100

        # Estimation CTR par position
        ctr = _estimate_ctr(position)

        # Trafic mensuel estimé si bien positionné
        trafic_mensuel = volume * ctr

        # Score business
        # Facteur 1: Volume × CTR (potentiel trafic)
        potentiel_trafic = min(100, (volume * ctr / 100) * 10)
        # Facteur 2: Intention commerciale
        intention_score = _intention_to_score(sujet.intention if hasattr(sujet, 'intention') else "informative")
        # Facteur 3: Valeur business (trafic × conversion × valeur)
        valeur_mensuelle = trafic_mensuel * taux_conversion * valeur_lead
        valeur_score = min(100, (valeur_mensuelle / 1000) * 50)

        raw = (potentiel_trafic * 0.35 + intention_score * 0.35 + valeur_score * 0.30)
        business_scores[sujet.nom] = round(min(100, max(0, raw)), 1)

    # Appliquer
    for sujet in state.sujets:
        if sujet.nom in business_scores:
            sujet.business_score = business_scores[sujet.nom]

    state.business_scores = business_scores
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st05", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    top3 = sorted(business_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    logger.info(f"ST05: {len(business_scores)} sujets scores — top3: {[(n, s) for n, s in top3]}")
    return state


def _estimate_ctr(position: float) -> float:
    """Estimation du CTR par position Google (basé sur études Advanced Web Ranking)."""
    if position <= 0:
        return 0.35
    if position <= 1:
        return 0.32
    elif position <= 3:
        return 0.18
    elif position <= 5:
        return 0.09
    elif position <= 10:
        return 0.04
    elif position <= 20:
        return 0.01
    else:
        return 0.005


def _intention_to_score(intention: str) -> float:
    return {
        "transactionnelle": 95.0,
        "comparative": 75.0,
        "locale": 70.0,
        "navigationnelle": 50.0,
        "informative": 40.0,
    }.get(intention, 40.0)
