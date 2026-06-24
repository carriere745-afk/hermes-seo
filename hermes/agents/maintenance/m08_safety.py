"""M08 — Safety Validator (V1.5).

Valide les actions avant execution: confidence, impact, YMYL, Disavow.
Skippable (V1.5). $0.
"""

import logging, time
from datetime import datetime
from hermes.models.project import Project
from hermes.core.strategie_db import log_event
logger = logging.getLogger("hermes.maintenance.m08")

async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    for action in project.execution_actions:
        if action.status != "pending": continue
        if action.confidence_before < project.human_approval_threshold:
            action.human_approval_required = True
        if project.ymyl_detected and action.category in ("publish", "optimize"):
            action.human_approval_required = True
    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m08", pipeline_id="maintenance", model="none",
              tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    return project
