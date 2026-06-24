"""ST04b — Competitive Feasibility Score.

Evalue la faisabilite de battre les concurrents sur chaque sujet.
Score 0-100 base sur : positions actuelles, autorite topique, ecart concurrentiel.
Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st04b")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st04b"
    state.phase = "analyse"

    feasibility: dict[str, int] = {}

    for sujet in state.sujets:
        score = _compute_feasibility(sujet, state)
        feasibility[sujet.nom] = score

    # Appliquer aux sujets
    for sujet in state.sujets:
        if sujet.nom in feasibility:
            sujet.feasibility_score = feasibility[sujet.nom]

    state.feasibility_scores = feasibility
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st04b", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    avg = sum(feasibility.values()) // max(len(feasibility), 1)
    logger.info(f"ST04b: {len(feasibility)} sujets scores — faisabilite moyenne {avg}/100")
    return state


def _compute_feasibility(sujet, state: StrategieState) -> int:
    score = 50  # Base neutre

    # 1. Topical Authority (+)
    ta = sujet.topical_authority if hasattr(sujet, 'topical_authority') else 50
    score += (ta - 50) * 0.3

    # 2. Position actuelle (si deja dans le top 20, plus facile)
    pos = sujet.position_moyenne if hasattr(sujet, 'position_moyenne') else 100
    if pos <= 3:
        score += 20
    elif pos <= 10:
        score += 10
    elif pos <= 20:
        score += 5
    elif pos > 50:
        score -= 15

    # 3. Nombre de concurrents
    n_conc = len(sujet.concurrents_top5) if hasattr(sujet, 'concurrents_top5') else 5
    if n_conc <= 1:
        score += 15
    elif n_conc <= 3:
        score += 5
    elif n_conc >= 5:
        score -= 10

    # 4. Volume (tres haut volume = plus de concurrence)
    vol = sujet.volume_total if hasattr(sujet, 'volume_total') else 0
    if vol > 10000:
        score -= 10
    elif vol > 1000:
        score -= 5

    # 5. Gap concurrentiel ST04
    for gap in state.gaps_concurrentiels:
        if hasattr(gap, 'keyword') and hasattr(sujet, 'keywords'):
            if gap.keyword in sujet.keywords:
                score += (gap.score_gap - 50) * 0.2
                break

    return min(100, max(0, int(score)))
