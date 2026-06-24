"""B08 — Moteur de Preuve SEO (V2).

Correle les backlinks acquis avec les évolutions de positions et trafic.
Skippable (V2). Les données sont collectées dès le MVP via B11/campaign_results.
"""

import logging
import time
from datetime import datetime
from hermes.models.backlinks import BacklinksState
from hermes.core.backlinks_db import get_db_stats
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b08")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b08"
    state.phase = "analyse"

    # V2 — utilise les campaign_results accumulés depuis le MVP
    try:
        stats = get_db_stats()
        n_results = stats.get("campaign_results", 0)
        if n_results > 0:
            logger.info(f"B08: {n_results} campaign results disponibles pour analyse de correlation")
    except Exception:
        pass

    logger.info("B08: Moteur de preuve SEO — correlations activees en V2")

    state.updated_at = datetime.now()
    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="b08", pipeline_id="backlinks",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    return state
