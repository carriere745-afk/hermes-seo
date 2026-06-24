"""L08 — Failure Analyzer (V1.5).

Apprend des echecs pour les eviter. Stocke les conditions d'exclusion
dans la table failures. M03 consulte ces donnees avant de dispatcher.
Skippable (V1.5). $0.
"""

import json, logging, time
from datetime import datetime
from uuid import uuid4
from hermes.models.project import Project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.learning.l08")


async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    new_failures = 0

    try:
        from hermes.core.project_db import _get_conn
        conn = _get_conn()
        failed = conn.execute(
            "SELECT * FROM execution_actions WHERE status='failed'"
        ).fetchall()
        conn.close()

        for f in failed:
            # Verifier si l'echec est deja enregistre
            conn2 = _get_conn()
            existing = conn2.execute(
                "SELECT id FROM failures WHERE action_type=? AND sector=?",
                (f["action_type"], project.secteur)
            ).fetchone()
            conn2.close()

            if not existing:
                do_not = {"secteur": project.secteur, "profile": project.profile}
                try:
                    c3 = _get_conn()
                    c3.execute(
                        "INSERT INTO failures (id, sector, profile, action_type, context, failure_reason, do_not_recommend_if, occurrences, created_at) "
                        "VALUES (?,?,?,?,?,?,?,1,?)",
                        (uuid4().hex[:12], project.secteur, project.profile,
                         f["action_type"],
                         json.dumps({"source_pipeline": f.get("source_pipeline", "")}),
                         f.get("execution_error", "Erreur inconnue"),
                         json.dumps(do_not), datetime.now().isoformat()))
                    c3.commit()
                    c3.close()
                    new_failures += 1
                except Exception:
                    pass

    except Exception as e:
        logger.debug(f"L08: {e}")

    if new_failures:
        logger.info(f"L08: {new_failures} nouveaux echecs analyses")

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="l08", pipeline_id="learning", model="none",
              tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"new_failures": new_failures})
    return project
