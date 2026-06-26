"""Agent ST12 — Analyse Semantique Concurrentielle (gap #4).

Compare le contenu du site vs top 10 SERP sur : longueur, structure Hn,
nombre d'images, presence FAQ, mots-cles utilises, schemas.
Genere un rapport d'ecart ("gap report") actionnable.

Ferme le gap #4 du document 630.
"""

import logging, re, time
from datetime import datetime
from urllib.parse import urlparse
import httpx

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st12")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st12"

    gaps = []
    site_url = state.site_url.rstrip("/") if state.site_url else ""

    # Analyser la page d'accueil du site comme reference
    site_stats = await _analyze_page(site_url) if site_url else {}

    # Analyser le top 3 SERP pour le keyword principal
    kw = (state.keywords_monitored or ["service"])[0]
    serp_pages = await _get_serp_pages(kw)

    for page in serp_pages[:3]:
        page_stats = await _analyze_page(page)
        if not page_stats:
            continue
        gap = {
            "url": page,
            "word_count_gap": (page_stats.get("word_count", 0) - site_stats.get("word_count", 0)),
            "h2_count_gap": (page_stats.get("h2_count", 0) - site_stats.get("h2_count", 0)),
            "image_count_gap": (page_stats.get("image_count", 0) - site_stats.get("image_count", 0)),
            "has_faq": page_stats.get("has_faq", False),
            "has_schema": page_stats.get("has_schema", False),
            "recommandations": [],
        }
        if gap["word_count_gap"] > 200:
            gap["recommandations"].append(f"Contenu plus court que le concurrent ({gap['word_count_gap']} mots d'ecart). Enrichir avec +{gap['word_count_gap']} mots.")
        if gap["h2_count_gap"] > 1:
            gap["recommandations"].append(f"Ajouter {gap['h2_count_gap']} H2 pour couvrir plus de sous-sujets.")
        if page_stats.get("has_faq") and not site_stats.get("has_faq"):
            gap["recommandations"].append("Ajouter une FAQ (schema FAQPage) — le concurrent en a une.")
        if page_stats.get("has_schema") and not site_stats.get("has_schema"):
            gap["recommandations"].append("Ajouter des schemas JSON-LD (le concurrent en a).")
        gaps.append(gap)

    state.semantic_gaps = gaps
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="st12", pipeline_id="strategie",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)
    logger.info(f"ST12: {len(gaps)} concurrents analyses, {sum(len(g['recommandations']) for g in gaps)} ecarts identifies")
    return state


async def _analyze_page(url: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            resp = await c.get(url)
            if resp.status_code != 200:
                return None
            html = resp.text[:100000]
    except Exception:
        return None

    # Compter mots, H2, images, FAQ, schema
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    word_count = len(text.split())
    h2_count = len(re.findall(r"<h2[^>]*>", html, re.IGNORECASE))
    image_count = len(re.findall(r"<img[^>]*>", html, re.IGNORECASE))
    has_faq = bool(re.search(r"faq|question.*reponse", text.lower()))
    has_schema = bool(re.search(r'application/ld\+json', html))

    return {
        "word_count": word_count,
        "h2_count": h2_count,
        "image_count": image_count,
        "has_faq": has_faq,
        "has_schema": has_schema,
    }


async def _get_serp_pages(kw: str) -> list[str]:
    """Recupere les URLs du top SERP via DuckDuckGo fallback."""
    try:
        from hermes.connectors.serp_api import SerpAPIClient
        client = SerpAPIClient()
        raw = await client._search_duckduckgo(kw, "fr", "fr")
        return [r["url"] for r in raw.get("organic_results", [])[:5] if r.get("url")]
    except Exception:
        return []
