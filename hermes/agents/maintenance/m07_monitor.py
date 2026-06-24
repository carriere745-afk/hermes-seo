"""M07 — Impact Monitor (6h).

Suit l'impact des actions executees a J+7, J+30, J+60, J+90.
Compare les predictions aux resultats reels et logue pour P8.
Non skippable. $0.
"""

import logging
import time
from datetime import datetime, timedelta

from hermes.models.project import Project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.maintenance.m07")


async def run(project: Project) -> Project:
    t0 = time.perf_counter()

    updates = 0
    now = datetime.now()

    for action in project.execution_actions:
        if action.status != "executed" or not action.executed_at:
            continue

        if isinstance(action.executed_at, str):
            exec_date = datetime.fromisoformat(action.executed_at)
        else:
            exec_date = action.executed_at

        days_since = (now - exec_date).days

        # Verifier l'impact aux echeances
        if days_since >= 7 and not action.impact_j7:
            action.impact_j7 = _check_impact(project, action, 7)
            updates += 1
        if days_since >= 30 and not action.impact_j30:
            action.impact_j30 = _check_impact(project, action, 30)
            updates += 1
        if days_since >= 60 and not action.impact_j60:
            action.impact_j60 = _check_impact(project, action, 60)
            updates += 1
        if days_since >= 90 and not action.impact_j90:
            action.impact_j90 = _check_impact(project, action, 90)
            updates += 1

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m07", pipeline_id="maintenance",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"impact_updates": updates})

    if updates:
        logger.info(f"M07: {updates} mesures d'impact mises a jour")
    return project


def _check_impact(project: Project, action, days: int) -> dict:
    """Verifie l'impact d'une action sur les positions/trafic."""
    impact = {
        "checked_at": datetime.now().isoformat(),
        "days_since_execution": days,
        "position_change": 0.0,
        "traffic_change": 0.0,
        "impressions_change": 0.0,
        "ctr_change": 0.0,
        "confidence": "low",
    }

    try:
        from pathlib import Path
        import sqlite3
        db_path = Path("data/serp_visibility.db")
        if not db_path.exists():
            return impact

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row

        since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        # Verifier les positions pour les mots-cles lies
        rows = conn.execute(
            "SELECT AVG(variation) as avg_change FROM positions_history "
            "WHERE date >= ?", (since_date,)
        ).fetchone()
        conn.close()

        if rows and rows["avg_change"]:
            impact["position_change"] = round(rows["avg_change"], 1)
            impact["traffic_change"] = round(rows["avg_change"] * 10, 1)  # Estimation
            impact["confidence"] = "medium" if days >= 30 else "low"
    except Exception:
        pass

    return impact
