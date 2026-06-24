"""L02 — Pattern Detector (heuristique en MVP, ML en V2).

Identifie les patterns de succes/echec par secteur et type d'action.
MVP: regles heuristiques simples.
Non skippable. $0.
"""

import json, logging, time
from datetime import datetime
from uuid import uuid4
from hermes.models.project import Project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.learning.l02")


async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    new_patterns = 0

    try:
        from hermes.core.project_db import _get_conn
        conn = _get_conn()

        # Analyser les actions executees pour trouver des patterns
        rows = conn.execute(
            "SELECT category, action_type, status, confidence_before, "
            "impact_j30, impact_j60 "
            "FROM execution_actions WHERE status='executed' AND impact_j30 != '{}'"
        ).fetchall()
        conn.close()

        patterns_by_type = {}
        for r in rows:
            key = f"{r['action_type']}_{project.secteur}_{project.profile}"
            if key not in patterns_by_type:
                patterns_by_type[key] = {"successes": 0, "total": 0}

            impact = json.loads(r.get("impact_j30", "{}"))
            if impact.get("position_change", 0) > 0:  # Impact positif
                patterns_by_type[key]["successes"] += 1
            patterns_by_type[key]["total"] += 1

        # Enregistrer les patterns significatifs
        for key, data in patterns_by_type.items():
            if data["total"] >= 5:
                success_rate = data["successes"] / data["total"]
                if success_rate >= 0.7 or success_rate <= 0.2:
                    atype, sector, profile = key.rsplit("_", 2)
                    _store_pattern(sector, profile, atype, success_rate, data["total"])
                    new_patterns += 1
                    logger.info(f"L02: Pattern {atype}/{sector}: taux succes={success_rate:.0%} "
                                f"({data['successes']}/{data['total']})")

    except Exception as e:
        logger.warning(f"L02: {e}")

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="l02", pipeline_id="learning",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"patterns_found": new_patterns})
    return project


def _store_pattern(sector: str, profile: str, action_type: str, success_rate: float, occurrences: int):
    try:
        from hermes.core.project_db import _get_conn
        conn = _get_conn()
        pid = f"P-{uuid4().hex[:6].upper()}"
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO patterns (id, pattern_id, sector, profile, action_type, context, resultat, occurrences, confidence, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (uuid4().hex[:12], pid, sector, profile, action_type,
             json.dumps({"secteur": sector, "profil": profile}),
             json.dumps({"taux_succes": round(success_rate, 2)}),
             occurrences, round(success_rate * 100),
             now, now))
        conn.commit()
        conn.close()
    except Exception:
        pass
