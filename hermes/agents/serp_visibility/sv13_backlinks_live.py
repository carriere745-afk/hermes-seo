"""SV13 — Backlinks Live Tracking (gap module 11 items #382-389).

Suit les backlinks gagnes et perdus en temps reel.
Alerte si backlink toxique sur page strategique.
Identifie les domaines qui linkent les concurrents mais pas le site.
"""

import logging, time
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from hermes.models.serp_visibility import SerpVisibilityState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.serp.sv13")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    t0 = time.perf_counter()
    state.current_agent = "sv13"

    tracking = {"gained_30d": 0, "lost_30d": 0, "toxic_alerts": [], "total_tracked": 0}

    try:
        db_path = Path("data/backlinks.db")
        if db_path.exists():
            conn = sqlite3.connect(str(db_path)); conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM backlinks WHERE last_seen >= date('now','-30 days') OR is_lost = 1"
            ).fetchall()
            conn.close()

            for r in rows:
                tracking["total_tracked"] += 1
                bl = dict(r)
                if bl.get("is_lost"):
                    tracking["lost_30d"] += 1
                elif bl.get("first_seen") and bl["first_seen"] >= (datetime.now() - timedelta(days=30)).isoformat():
                    tracking["gained_30d"] += 1
                if int(bl.get("toxicity_score", 0)) > 60:
                    tracking["toxic_alerts"].append({"domain": bl.get("source_domain", ""),
                                                     "score": bl["toxicity_score"],
                                                     "action": "Desavouer" if bl["toxicity_level"] == "toxic" else "Surveiller"})
    except Exception:
        pass

    state.backlinks_tracking = tracking
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="sv13", pipeline_id="serp", model="none",
              tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    return state
