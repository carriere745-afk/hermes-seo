"""M10 — Dependency Manager (V1.5).

Gere les dependances entre actions (A depend de B).
Skippable (V1.5). $0.
"""

import json, logging, time
from datetime import datetime
from hermes.models.project import Project
from hermes.core.strategie_db import log_event
logger = logging.getLogger("hermes.maintenance.m10")

DEPENDENCY_MAP = {
    "creer_backlink": ["creer_pilier", "creer_article"],
    "notifier_indexnow": ["generer_llms_txt"],
    "envoyer_email": ["generer_email_crm"],
}

async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    for action in project.execution_actions:
        if action.status != "pending": continue
        deps = DEPENDENCY_MAP.get(action.action_type, [])
        if deps:
            action.description += f" [Depend de: {', '.join(deps)}]"
    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m10", pipeline_id="maintenance", model="none",
              tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    return project
