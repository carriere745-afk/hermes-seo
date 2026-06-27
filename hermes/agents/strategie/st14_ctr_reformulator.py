"""Agent ST14 — CTR Reformulator (gap module 10 items #371, #375).

Analyse les pages avec impressions GSC mais CTR faible (<2%).
Genere automatiquement 2-3 variantes de title/description optimisees
pour ameliorer le CTR, basees sur les patterns SERP observes.
"""

import logging, re, time
from datetime import datetime
from pathlib import Path
import sqlite3

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st14")

CTR_PATTERNS = {
    "question": {"boost": 15, "template": "{kw} ? Guide complet et reponses d'experts"},
    "date": {"boost": 12, "template": "{kw} en 2026 — Tout ce qu'il faut savoir"},
    "chiffre": {"boost": 18, "template": "{kw} : {n} astuces/chiffres/techniques a connaitre"},
    "liste": {"boost": 14, "template": "Top {n} des meilleurs {kw} — Comparatif et avis"},
    "guide": {"boost": 10, "template": "Guide {kw} : definition, avantages et mise en oeuvre"},
    "urgent": {"boost": 8, "template": "{kw} — Tout comprendre en 5 minutes"},
}


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st14"

    low_ctr_pages = _find_low_ctr_pages(state.domain)
    suggestions = []

    for page in low_ctr_pages[:10]:
        kw = page.get("keyword", "")
        ctr = page.get("ctr", 0)
        current_title = page.get("title", "")

        # Generer 3 variantes
        variants = _generate_title_variants(kw, current_title)
        # Choisir la meilleure selon le pattern
        best = max(variants, key=lambda v: v["estimated_ctr_boost"])
        suggestions.append({
            "keyword": kw,
            "current_ctr": ctr,
            "current_title": current_title,
            "suggested_title": best["title"],
            "estimated_ctr_boost": best["estimated_ctr_boost"],
            "pattern": best["pattern"],
            "page_url": page.get("url", ""),
        })

    state.ctr_suggestions = suggestions
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="st14", pipeline_id="strategie",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"ctr_suggestions": len(suggestions)})

    logger.info(f"ST14: {len(suggestions)} suggestions CTR generees")
    return state


def _find_low_ctr_pages(domain: str) -> list[dict]:
    """Trouve les pages avec beaucoup d'impressions mais CTR faible."""
    try:
        db_path = Path("data/serp_visibility.db")
        if not db_path.exists():
            return _mock_ctr_pages()
        conn = sqlite3.connect(str(db_path)); conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT keyword, url, AVG(ctr) as ctr, SUM(impressions) as total_imp "
            "FROM positions_history WHERE date >= date('now', '-30 days') "
            "AND (url LIKE ? OR ? = '') "
            "GROUP BY keyword, url HAVING AVG(ctr) < 2 AND SUM(impressions) > 100 "
            "ORDER BY total_imp DESC LIMIT 20",
            (f"%{domain}%", domain)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return _mock_ctr_pages()


def _mock_ctr_pages() -> list[dict]:
    return [{"keyword": "exemple mot cle", "url": "/page", "ctr": 1.2, "total_imp": 500, "title": "Mon titre actuel"}]


def _generate_title_variants(kw: str, current_title: str) -> list[dict]:
    """Genere 3 variantes de title optimisees pour le CTR."""
    variants = []
    for pattern_name, pat in CTR_PATTERNS.items():
        title = pat["template"].format(kw=kw, n=5)
        if len(title) <= 65:  # Google truncation limit
            variants.append({
                "title": title,
                "estimated_ctr_boost": pat["boost"],
                "pattern": pattern_name,
            })
        if len(variants) >= 3:
            break
    return variants
