"""B10 — Authority Graph (V2).

Analyse la proximité du site avec les hubs d'autorité.
Skippable (V2). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from hermes.models.backlinks import BacklinksState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b10")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b10"
    state.phase = "analyse"

    # Classer les domaines par DR pour identifier les hubs
    hubs = sorted(state.referring_domains, key=lambda d: d.domain_rating, reverse=True)[:20]
    authority_graph = {
        "hubs": [{"domain": h.domain, "dr": h.domain_rating, "type": h.domain_type} for h in hubs],
        "total_domains": len(state.referring_domains),
        "avg_dr": round(sum(d.domain_rating for d in state.referring_domains) / max(len(state.referring_domains), 1), 1),
    }
    state.authority_graph = authority_graph
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="b10", pipeline_id="backlinks",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)

    logger.info(f"B10: Authority Graph — {len(hubs)} hubs identifies")
    return state
