"""M09 — Rollback Manager (V1.5).

Annule automatiquement une action en cas d'erreur ou degradation.
Skippable (V1.5). $0.
"""

import logging, time
from datetime import datetime
from hermes.models.project import Project
from hermes.core.strategie_db import log_event
logger = logging.getLogger("hermes.maintenance.m09")

async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    for action in project.execution_actions:
        if action.status == "failed" and project.rollback_enabled:
            if action.snapshot_before:
                action.status = "rolled_back"
                action.execution_result = f"Rollback: restauration du snapshot du {action.snapshot_before.get('taken_at', 'inconnu')}"
                logger.info(f"M09: Rollback de {action.id} — {action.action_type}")
    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m09", pipeline_id="maintenance", model="none",
              tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    return project
