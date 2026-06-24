"""B05b — Broken Link Building (V1.5).

Detecte les liens cassés sur les domaines referents/prospects
et propose des remplacements par du contenu du site.
Skippable (V1.5). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from hermes.models.backlinks import BacklinksState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b05b")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b05b"
    state.phase = "analyse"

    # Skippable en V1.5 — prépare juste les données
    logger.info("B05b: Broken link building — détection différée (V1.5)")

    state.updated_at = datetime.now()
    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="b05b", pipeline_id="backlinks",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    return state
