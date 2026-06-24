"""L05 — Model Distributor.

Synchronise le modele global vers les instances clients (anonymise).
Opt-in explicite requis. Non skippable. $0.
"""

import logging, time
from hermes.models.project import Project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.learning.l05")


async def run(project: Project) -> Project:
    t0 = time.perf_counter()

    # Verifier l'opt-in (par defaut false en MVP)
    opt_in = project.local_seo.get("learning_opt_in", False)

    if opt_in:
        logger.info(f"L05: Distribution activee pour {project.id}")
        # En V1.5: synchroniser les patterns anonymises vers l'instance client
    else:
        logger.info(f"L05: Opt-in non active pour {project.id} — distribution desactivee")

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="l05", pipeline_id="learning",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"opt_in": opt_in})
    return project
