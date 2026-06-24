"""ST08 — Fusion / Separation.

Recommandations de fusion, separation ou suppression de pages
basees sur P2 (qualite) + P3 (technique) + P4 (cannibalisation).
Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st08")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st08"
    state.phase = "analyse"

    recommendations: list[dict] = []

    # 1. Traiter les cannibalisations de ST02 → fusions
    for cannib in state.cannibalisations:
        gravite = cannib.get("gravite", "low")
        if gravite in ("critical", "high"):
            pages = cannib.get("pages_concernees", [])
            if len(pages) >= 2:
                recommendations.append({
                    "type": "fusion",
                    "pages": pages,
                    "keyword": cannib.get("keyword", ""),
                    "raison": f"Cannibalisation {gravite}",
                    "action": f"Fusionner {pages[0]} et {pages[1]} en une page unique optimisee",
                    "impact": "elimine competition interne, consolide l'autorite",
                })

    # 2. Pages fines (P2+P3) → suppression
    thin_pages = _find_thin_pages(state)
    for tp in thin_pages:
        recommendations.append({
            "type": "suppression",
            "pages": [tp["url"]],
            "keyword": tp.get("title", ""),
            "raison": "Page sans contenu substantiel (thin content)",
            "action": f"Supprimer ou rediriger {tp['url']}",
            "impact": "nettoie l'index, concentre le budget crawl",
        })

    # 3. Silo fusionnable
    for silo in state.silos_analysis:
        if silo.get("volume_total", 0) < 100 and silo.get("sujets_couverts", 0) <= 1:
            recommendations.append({
                "type": "fusion_silo",
                "pages": [],
                "keyword": silo.get("silo", ""),
                "raison": "Silo a faible volume, couverture insuffisante",
                "action": f"Fusionner le silo '{silo.get('silo')}' dans un silo parent plus large",
                "impact": "consolide l'autorite thematique",
            })

    state.fusion_separation = recommendations
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st08", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    n_fusions = sum(1 for r in recommendations if r["type"] in ("fusion", "fusion_silo"))
    n_suppressions = sum(1 for r in recommendations if r["type"] == "suppression")
    logger.info(f"ST08: {n_fusions} fusions, {n_suppressions} suppressions recommandees")
    return state


def _find_thin_pages(state: StrategieState) -> list[dict]:
    """Trouve les pages a faible contenu (thin content)."""
    thin = []
    try:
        db_path = Path("data/audit_contenu.db")
        if db_path.exists():
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT url, title, score_global FROM pages WHERE score_global < 30 "
                "ORDER BY score_global ASC LIMIT 20"
            ).fetchall()
            conn.close()
            for r in rows:
                thin.append({"url": r["url"], "title": r["title"], "score": r["score_global"]})
    except Exception:
        pass

    # Fallback : utiliser les sujets a faible volume + non couverts
    for sujet in state.sujets:
        if hasattr(sujet, 'volume_total') and sujet.volume_total < 50 and not sujet.couvert:
            pass  # On ne les supprime pas, on les ignore juste

    return thin
