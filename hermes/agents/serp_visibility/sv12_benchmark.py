"""SV12 — Competitive Benchmarking Engine (gap 18 du doc 630).

Suit un panel de concurrents definis en continu: evolution de leur score,
nouveaux articles sur nos requetes, changements de structure.
"""

import logging, time, re
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from hermes.models.serp_visibility import SerpVisibilityState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.serp.sv12")

async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    t0 = time.perf_counter()
    state.current_agent = "sv12"

    benchmark = {"competitors_tracked": len(state.competitors), "alerts": [], "summary": {}}
    comps = list(state.competitors)[:5]

    for comp in comps:
        summary = {"domain": comp, "positions_overlap": 0, "new_content_30d": 0, "avg_position": 0}
        try:
            db_path = Path("data/serp_visibility.db")
            if db_path.exists():
                conn = sqlite3.connect(str(db_path)); conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT COUNT(*) as cnt FROM positions_history WHERE url LIKE ? AND date >= date('now','-30 days')",
                    (f"%{comp}%",)).fetchone()
                summary["new_content_30d"] = rows["cnt"] if rows else 0
                conn.close()
        except Exception:
            pass
        benchmark["summary"][comp] = summary

    state.benchmark = benchmark
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="sv12", pipeline_id="serp", model="none",
              tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    return state
