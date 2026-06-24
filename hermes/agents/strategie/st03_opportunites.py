"""ST03 — Opportunites.

Identifie les requetes sans page dediee (opportunites de contenu).
Utilise P4 S05 (content gaps) + GSC si disponible.
Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st03")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st03"
    state.phase = "analyse"

    opportunites: list[dict] = []

    # 1. Sujets non couverts de ST01 = opportunites
    for sujet in state.sujets:
        if not sujet.couvert and sujet.volume_total > 0:
            score = _compute_opportunity_score(sujet)
            opportunites.append({
                "sujet": sujet.nom,
                "keywords": sujet.keywords,
                "volume_total": sujet.volume_total,
                "volume_principal": sujet.volume_principal,
                "intention": sujet.intention,
                "silo": sujet.silo,
                "type_page_recommande": _recommend_page_type(sujet),
                "opportunite_score": score,
                "position_moyenne": sujet.position_moyenne,
                "concurrents_top5": sujet.concurrents_top5,
            })

    # 2. Ajouter les gaps P4 (content gaps S05) si disponibles
    p4_gaps = _load_p4_gaps()
    for gap in p4_gaps:
        kw = gap.get("keyword", "")
        if not any(o["sujet"] and kw in o.get("keywords", []) for o in opportunites):
            opportunites.append({
                "sujet": kw,
                "keywords": [kw],
                "volume_total": gap.get("search_volume", 100),
                "volume_principal": gap.get("search_volume", 100),
                "intention": gap.get("intention", "informative"),
                "silo": gap.get("silo", "general"),
                "type_page_recommande": gap.get("type_page", "article"),
                "opportunite_score": gap.get("opportunity_score", 60),
                "position_moyenne": 100.0,
                "concurrents_top5": gap.get("competitors", []),
            })

    # Trier par score d'opportunite decroissant
    opportunites.sort(key=lambda o: o["opportunite_score"], reverse=True)

    state.opportunites = opportunites
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st03", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST03: {len(opportunites)} opportunites identifiees")
    return state


def _compute_opportunity_score(sujet) -> int:
    """Score 0-100 base sur volume, gap positionnel, intention."""
    score = 0
    # Volume
    if sujet.volume_total > 10000:
        score += 30
    elif sujet.volume_total > 1000:
        score += 20
    elif sujet.volume_total > 100:
        score += 10

    # Gap positionnel (si on est loin)
    pos = sujet.position_moyenne if hasattr(sujet, 'position_moyenne') else 100
    if pos > 50:
        score += 25
    elif pos > 20:
        score += 15
    elif pos > 10:
        score += 10

    # Intention
    if hasattr(sujet, 'intention'):
        if sujet.intention == "transactionnelle":
            score += 25
        elif sujet.intention == "comparative":
            score += 20
        elif sujet.intention == "informative":
            score += 15

    # Concurrence (peu de concurrents = plus facile)
    n_conc = len(sujet.concurrents_top5) if hasattr(sujet, 'concurrents_top5') else 0
    if n_conc <= 1:
        score += 20
    elif n_conc <= 3:
        score += 10

    return min(100, score)


def _recommend_page_type(sujet) -> str:
    if hasattr(sujet, 'intention'):
        if sujet.intention == "transactionnelle":
            return "fiche_produit" if sujet.volume_total < 1000 else "landing"
        elif sujet.intention == "comparative":
            return "comparatif"
        elif sujet.intention == "locale":
            return "service_local"
    return "article"


def _load_p4_gaps() -> list[dict]:
    try:
        db_path = Path("data/serp_visibility.db")
        if not db_path.exists():
            return []
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT keyword, search_volume, position FROM positions_history "
            "WHERE date >= date('now', '-30 days') AND position > 10 "
            "GROUP BY keyword ORDER BY search_volume DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return [{"keyword": r["keyword"], "search_volume": r["search_volume"] or 100} for r in rows]
    except Exception:
        return []
