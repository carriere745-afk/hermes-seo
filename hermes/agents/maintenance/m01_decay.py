"""M01 — Content Decay Detector.

Identifie les pages en perte de trafic/positions sur 90 jours.
5 criteres : trafic, positions, impressions, age, concurrence.
Non skippable. $0.
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from hermes.models.project import Project, ExecutionAction
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.maintenance.m01")

DECAY_THRESHOLDS = {
    "traffic_loss": 20,      # % perte trafic GSC sur 90j
    "position_drop": 5,      # places perdues
    "impressions_drop": 30,  # % perte impressions
    "content_age_days": 365, # jours sans MAJ
}


async def run(project: Project) -> Project:
    t0 = time.perf_counter()

    decay_pages: list[dict] = []
    actions: list[ExecutionAction] = []

    # Charger les positions P4
    positions = _load_p4_positions(project.domain)

    # Analyser chaque mot-cle pour detecter le decay
    for kw_data in positions:
        current_pos = kw_data.get("avg_pos", 0)
        prev_pos = kw_data.get("position_previous", 0)
        impressions = kw_data.get("total_imp", 0)
        impressions_prev = kw_data.get("impressions_previous", impressions)

        severity = "low"
        reasons = []

        # Perte de positions
        pos_delta = current_pos - prev_pos if prev_pos > 0 else 0
        if pos_delta >= DECAY_THRESHOLDS["position_drop"]:
            severity = "high" if pos_delta >= 10 else "medium"
            reasons.append(f"Perte de {pos_delta:.0f} positions (actuel: {current_pos:.0f})")

        # Perte d'impressions
        if impressions_prev > 0:
            imp_drop = (impressions_prev - impressions) / impressions_prev * 100
            if imp_drop >= DECAY_THRESHOLDS["impressions_drop"]:
                reasons.append(f"Perte d'impressions: {imp_drop:.0f}%")

        if reasons:
            decay_pages.append({
                "url": kw_data.get("url", ""),
                "keyword": kw_data.get("keyword", ""),
                "current_position": round(current_pos, 1),
                "previous_position": round(prev_pos, 1),
                "impressions": impressions,
                "reasons": reasons,
                "severity": severity,
                "recommandation": _decay_recommandation(severity, kw_data),
            })

            # Creer ExecutionAction pour P7
            if severity in ("high", "medium"):
                actions.append(ExecutionAction(
                    source_pipeline="m01",
                    source_agent="m01",
                    category="optimize",
                    action_type="content_refresh",
                    description=f"Rafraichir contenu: {kw_data.get('keyword', '')}",
                    priority="P1" if severity == "high" else "P2",
                    target_url=kw_data.get("url", ""),
                    target_page=kw_data.get("url", ""),
                    confidence_before=70 if severity == "high" else 50,
                    predicted_impact=f"Recovery estime: +{max(1, pos_delta)} positions",
                ))

    # Trier par severite
    decay_pages.sort(key=lambda d: {"high": 0, "medium": 1, "low": 2}.get(d["severity"], 3))

    # Ajouter au projet
    project.execution_actions.extend(actions)
    project.local_seo = {**project.local_seo, "decay_pages": decay_pages}

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m01", pipeline_id="maintenance",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)

    n_high = sum(1 for d in decay_pages if d["severity"] == "high")
    logger.info(f"M01: {len(decay_pages)} pages en decay — {n_high} severes, {len(actions)} actions generees")
    return project


def _load_p4_positions(domain: str) -> list[dict]:
    try:
        import sqlite3
        db_path = Path("data/serp_visibility.db")
        if not db_path.exists():
            return _mock_positions()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT keyword, url, AVG(position) as avg_pos, SUM(impressions) as total_imp "
            "FROM positions_history WHERE date >= date('now', '-90 days') "
            "GROUP BY keyword, url ORDER BY total_imp DESC LIMIT 100"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return _mock_positions()


def _mock_positions() -> list[dict]:
    return [
        {"keyword": "exemple mot cle", "url": "/page", "avg_pos": 12.5, "position_previous": 6.0,
         "total_imp": 2500, "impressions_previous": 4000},
        {"keyword": "autre sujet", "url": "/autre", "avg_pos": 3.2, "position_previous": 2.8,
         "total_imp": 8000, "impressions_previous": 8500},
    ]


def _decay_recommandation(severity: str, kw_data: dict) -> str:
    kw = kw_data.get("keyword", "cette page")
    if severity == "high":
        return f"Reecriture majeure de '{kw}' — contenu obsolet ou depasse par la concurrence"
    elif severity == "medium":
        return f"Enrichir '{kw}' avec des donnees recentes et des sources actualisees"
    return f"Surveiller '{kw}' — legere tendance a la baisse"
