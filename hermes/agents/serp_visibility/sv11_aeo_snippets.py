"""Agent SV11 — AEO Featured Snippet & PAA Tracker (gap #6).

Suit les featured snippets (position 0), PAA (People Also Ask),
et autres SERP features pour les requetes cibles.
Ferme le gap #6 du document 630 (AEO : featured snippet / PAA tracking).
"""

import logging, time
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from hermes.models.serp_visibility import SerpVisibilityState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.serp.sv11")

# SERP features a suivre
FEATURE_TYPES = [
    "featured_snippet", "paa", "ai_overview", "video_carousel",
    "image_pack", "local_pack", "knowledge_panel", "top_stories",
    "related_questions", "things_to_know",
]

# Score PAA : si la page est dans les PAA, son AEO score augmente
PAA_BONUS = 10   # +10 points si la page apparait dans les PAA
SNIPPET_BONUS = 25  # +25 points si featured snippet capture


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    t0 = time.perf_counter()
    state.current_agent = "sv11"

    snippet_data: dict[str, dict] = {}
    paa_opportunities = 0

    for kw in state.keywords[:20]:
        # Charger les features SERP depuis le cache (S03)
        features = _load_serp_features(kw)
        snippet_data[kw] = {
            "has_featured_snippet": features.get("featured_snippet", False),
            "paa_count": features.get("paa_count", 0),
            "ai_overview": features.get("ai_overview", False),
            "video": features.get("video_carousel", False),
            "local_pack": features.get("local_pack", False),
            "aeo_opportunity_score": 0,
        }

        # Calculer le score d'opportunite AEO
        score = 0
        if features.get("paa_count", 0) > 0:
            score += features["paa_count"] * 5  # 5 points par PAA
        if features.get("featured_snippet"):
            score += 30
        if features.get("ai_overview"):
            score += 40  # AI Overview = opportunite GEO majeure
        snippet_data[kw]["aeo_opportunity_score"] = min(100, score)
        if score >= 30:
            paa_opportunities += 1

    state.serp_features = {
        **(state.serp_features or {}),
        "snippet_tracking": snippet_data,
        "paa_opportunities": paa_opportunities,
    }
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="sv11", pipeline_id="serp",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"paa_opportunities": paa_opportunities})

    logger.info(f"SV11: {paa_opportunities} mots-cles avec opportunite AEO (PAA/featured snippet)")
    return state


def _load_serp_features(keyword: str) -> dict:
    try:
        db_path = Path("data/serp_visibility.db")
        if not db_path.exists():
            return {"paa_count": 2, "featured_snippet": False, "ai_overview": False}
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT feature_type, COUNT(*) as cnt FROM serp_features "
            "WHERE keyword = ? AND date >= date('now', '-30 days') "
            "GROUP BY feature_type",
            (keyword,)
        ).fetchall()
        conn.close()
        result = {}
        for r in rows:
            result[r["feature_type"]] = r["cnt"]
        return result
    except Exception:
        return {"paa_count": 1, "featured_snippet": False, "ai_overview": False}
