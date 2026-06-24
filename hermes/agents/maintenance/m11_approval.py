"""M11 — Human Approval Gateway (V1.5).

Separe les actions auto des actions necessitant validation humaine.
Skippable (V1.5). $0.
"""

import logging, time
from hermes.models.project import Project
from hermes.core.strategie_db import log_event
logger = logging.getLogger("hermes.maintenance.m11")

AUTO_ACTIONS = ["generer_llms_txt", "generer_sitemap", "generer_meta_description", "publier_cms"]

async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    for action in project.execution_actions:
        if action.status != "pending": continue
        if action.action_type in AUTO_ACTIONS or action.confidence_before >= 80:
            action.human_approval_required = False
        elif action.confidence_before < 60 or project.human_approval_threshold <= 60:
            action.human_approval_required = True
    log_event(session_id=project.id, agent_id="m11", pipeline_id="maintenance", model="none",
              tokens_used=0, cost=0.0, duration_ms=int((time.perf_counter()-t0)*1000), success=True)
    return project
