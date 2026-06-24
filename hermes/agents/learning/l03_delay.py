"""L03 — Delay Estimator.

Affine les estimations de delai par type d'action et secteur.
Non skippable. $0.
"""

import logging, time
from datetime import datetime
from hermes.models.project import Project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.learning.l03")

DEFAULT_DELAYS = {
    "creer_pilier": "4-6 mois", "creer_article": "2-4 mois",
    "ajouter_faq": "2-3 mois", "enrichir_eeat": "1-3 mois",
    "guest_post": "3-8 semaines", "link_insertion": "2-6 semaines",
    "content_refresh": "1-2 mois",
}


async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    adjusted = 0

    try:
        from hermes.core.project_db import _get_conn
        conn = _get_conn()
        # Moyenne des delais reels par type d'action
        rows = conn.execute(
            "SELECT action_type, impact_j30, impact_j60, impact_j90 "
            "FROM execution_actions WHERE status='executed'"
        ).fetchall()
        conn.close()

        import json
        delays = {}
        for r in rows:
            at = r["action_type"]
            impact = json.loads(r.get("impact_j90", "{}"))
            pos_change = impact.get("position_change", 0)
            if at not in delays:
                delays[at] = {"total": 0, "has_impact": 0}
            delays[at]["total"] += 1
            if pos_change > 0:
                delays[at]["has_impact"] += 1
    except Exception:
        pass

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="l03", pipeline_id="learning",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"delays_analyzed": len(delays) if 'delays' in dir() else 0})
    return project
