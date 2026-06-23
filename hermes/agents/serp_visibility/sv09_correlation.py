"""S09 — Correlation Actions / Positions.

Met en relation les actions Hermes (publication P1, correction P3) avec
les evolutions de positions. Calcule les deltas a J+7, J+30, J+60, J+90.

confidence_score : High / Medium / Low selon coherence temporelle
et absence de Core Update.

LLM Haiku pour formuler les conclusions.

$0 (+ Haiku en premium).
"""

import logging
from datetime import datetime, timedelta

from hermes.models.serp_visibility import SerpVisibilityState, CorrelationEntry

logger = logging.getLogger("hermes.serp.sv09")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv09"
    if state.mode == "fast":
        return state

    # Recuperer les actions recentes
    try:
        from hermes.core.serp_db import get_actions_since
        actions = get_actions_since(days=90)
    except Exception:
        actions = []

    if not actions:
        logger.info("S09: aucune action recente a correler")
        return state

    correlations = []
    for action in actions[:20]:
        url = action.get("url", "")
        action_date_str = action.get("date", "")
        try:
            action_date = datetime.fromisoformat(action_date_str)
        except Exception:
            continue

        # Recuperer les positions avant/ apres
        try:
            from hermes.core.serp_db import get_positions_for_keyword
        except Exception:
            continue

        # Chercher les mots-cles pour cette URL
        for pos_entry in state.positions[:30]:
            if pos_entry.url.rstrip("/") != url.rstrip("/"):
                continue

            kw = pos_entry.keyword
            history = get_positions_for_keyword(kw, days=90)
            if len(history) < 3:
                continue

            # Position avant l'action
            before = [r for r in history if r["date"] < action_date_str]
            after = [r for r in history if r["date"] >= action_date_str]

            if not before or not after:
                continue

            pos_before = sum(r["position"] for r in before[-7:]) / max(1, len(before[-7:]))

            # Deltas
            def pos_at_days(days: int) -> float:
                target = action_date + timedelta(days=days)
                candidates = [r for r in history if r["date"] >= target.isoformat()[:10]]
                if not candidates:
                    return pos_before
                return sum(r["position"] for r in candidates[:7]) / max(1, len(candidates[:7]))

            j7 = round(pos_at_days(7) - pos_before, 1)
            j30 = round(pos_at_days(30) - pos_before, 1)
            j60 = round(pos_at_days(60) - pos_before, 1)
            j90 = round(pos_at_days(90) - pos_before, 1)

            confidence = _confidence_score(j7, j30, j60, j90, state.core_update_detected)

            correlations.append(CorrelationEntry(
                action_id=str(action.get("id", "")),
                url=url,
                keyword=kw,
                delta_j7=j7,
                delta_j30=j30,
                delta_j60=j60,
                delta_j90=j90,
                confidence_score=confidence,
                pattern="",
            ))

    state.correlations = correlations

    if correlations:
        positive = sum(1 for c in correlations if c.delta_j30 < 0)
        logger.info(f"S09: {len(correlations)} correlations, {positive} positives")

    state.updated_at = datetime.now()
    return state


def _confidence_score(j7: float, j30: float, j60: float, j90: float, core_update: bool) -> str:
    if core_update:
        return "Low"
    same_direction = (j7 <= 0 and j30 <= 0) or (j7 >= 0 and j30 >= 0)
    consistent = same_direction and (abs(j30 - j60) < 3) and (abs(j60 - j90) < 3)
    if consistent and abs(j30) > 2:
        return "High"
    if same_direction:
        return "Medium"
    return "Low"
