"""L00 — Superviseur Learning.

Initialise le pipeline, charge les donnees, verifie le volume minimum.
Non skippable. $0.
"""

import logging, time
from datetime import datetime
from hermes.models.project import Project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.learning.l00")

MIN_PREDICTIONS = 10
CALIBRATION_THRESHOLD = 50

async def run(project: Project) -> Project:
    t0 = time.perf_counter()

    # Verifier le volume de donnees
    try:
        from hermes.core.strategie_db import _get_conn as s_conn
        conn = s_conn()
        n_preds = conn.execute("SELECT COUNT(*) FROM predictions_history").fetchone()[0]
        conn.close()
        ready = n_preds >= MIN_PREDICTIONS
        logger.info(f"L00: {n_preds} predictions — {'pret' if ready else 'accumulation silencieuse'} "
                    f"(seuil calibration: {CALIBRATION_THRESHOLD})")
    except Exception:
        n_preds = 0
        ready = False

    project.updated_at = datetime.now()
    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="l00", pipeline_id="learning",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"predictions_available": n_preds, "ready": ready})
    return project
