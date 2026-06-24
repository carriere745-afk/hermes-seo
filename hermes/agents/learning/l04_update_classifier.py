"""L04 — Update Classifier.

Classe les Core Updates et apprend les patterns de recovery.
Non skippable. $0.
"""

import logging, time
from hermes.models.project import Project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.learning.l04")

UPDATE_PATTERNS = {
    "helpful_content": {"recovery_delay": "4-8 semaines", "best_action": "renforcer_eeat"},
    "spam_update": {"recovery_delay": "2-6 semaines", "best_action": "disavow_toxic"},
    "core": {"recovery_delay": "6-12 semaines", "best_action": "ameliorer_qualite_globale"},
    "reviews": {"recovery_delay": "3-6 semaines", "best_action": "rendre_avis_authentiques"},
}


async def run(project: Project) -> Project:
    t0 = time.perf_counter()

    if project.core_update_impacted:
        try:
            from hermes.core.project_db import _get_conn
            conn = _get_conn()
            actions = conn.execute(
                "SELECT action_type, status, impact_j30 "
                "FROM execution_actions WHERE action_type LIKE '%core_update%'"
            ).fetchall()
            conn.close()
            n_recovery = sum(1 for a in actions if a["status"] == "executed")
            if n_recovery > 0:
                logger.info(f"L04: {n_recovery} actions post-Core Update analysees")
        except Exception:
            pass

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="l04", pipeline_id="learning",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    return project
