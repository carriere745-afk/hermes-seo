"""L07 — Recommendation Optimizer (V1.5).

Analyse les patterns et genere des correction_factor pour P5.
Flux de retroaction P8 → P5 via predictions_history.correction_factor.
Skippable (V1.5). $0.
"""

import json, logging, time
from datetime import datetime
from uuid import uuid4
from hermes.models.project import Project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.learning.l07")


async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    corrections = 0

    try:
        from hermes.core.project_db import _get_conn
        conn = _get_conn()
        patterns = conn.execute(
            "SELECT * FROM patterns WHERE occurrences >= 10 AND confidence >= 70"
        ).fetchall()
        conn.close()

        for p in patterns:
            sector = p["sector"]
            action_type = p["action_type"]
            taux = json.loads(p.get("resultat", "{}")).get("taux_succes", 0.5)

            # Generer le correction_factor
            correction = {"action_type": action_type, "sector": sector,
                          "taux_succes": taux, "coefficient": round(taux, 2)}

            try:
                from hermes.core.strategie_db import _get_conn as s_conn
                sconn = s_conn()
                sconn.execute(
                    "UPDATE predictions_history SET correction_factor = ? WHERE action_type = ?",
                    (json.dumps(correction), action_type))
                sconn.commit()
                sconn.close()
                corrections += 1
            except Exception:
                pass

            if corrections > 0:
                logger.info(f"L07: {corrections} correction_factors injectes dans predictions_history")

    except Exception as e:
        logger.debug(f"L07: {e}")

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="l07", pipeline_id="learning", model="none",
              tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"corrections_injected": corrections})
    return project
