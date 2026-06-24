"""B09 — Link Scarcity & Velocity (V2).

Analyse la rareté des liens (nombre de liens sortants par domaine)
et la vitesse d'acquisition des concurrents.
Skippable (V2). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from hermes.models.backlinks import BacklinksState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b09")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b09"
    state.phase = "analyse"

    scarcity: dict[str, float] = {}
    for d in state.referring_domains:
        n_bl = d.backlinks_count
        rarity = max(0, 100 - n_bl * 5)
        scarcity[d.domain] = round(rarity, 1)

    state.scarcity_scores = scarcity
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="b09", pipeline_id="backlinks",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)

    logger.info(f"B09: Link Scarcity calcule pour {len(scarcity)} domaines")
    return state
