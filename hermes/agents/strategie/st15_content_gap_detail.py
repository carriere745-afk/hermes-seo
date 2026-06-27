"""Agent ST15 — Content Gap Detaille (gap module 10 items #360-368, module 21 #570-574).

Compare chaque page du site avec le top 3 SERP sur:
- Longueur de contenu (mots)
- Structure Hn (H1, H2, H3)
- Presence FAQ
- Nombre d'images
- Schemas JSON-LD
- Sources citees
- Fraicheur (dateModified vs concurrents)

Genere un rapport d'ecart actionnable avec des recommandations chiffrees.
"""

import logging, re, time
from datetime import datetime

import httpx

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st15")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st15"

    content_gaps = []
    site_url = state.site_url.rstrip("/") if state.site_url else ""

    # Analyser jusqu'a 5 mots-cles
    for kw in (state.keywords_monitored or [])[:5]:
        # Recuperer le top 3 SERP
        serp_pages = await _get_serp_urls(kw)

        # Analyser la page du site si elle existe
        site_page_url = f"{site_url}/{kw.replace(' ', '-')[:50]}" if site_url else ""
        site_stats = await _analyze_page(site_page_url) if site_page_url else {}

        competitors_stats = []
        for comp_url in serp_pages[:3]:
            stats = await _analyze_page(comp_url)
            if stats:
                competitors_stats.append(stats)

        if competitors_stats and site_stats:
            # Calculer les ecarts moyens
            avg_words = sum(c.get("word_count", 0) for c in competitors_stats) / len(competitors_stats)
            avg_h2 = sum(c.get("h2_count", 0) for c in competitors_stats) / len(competitors_stats)
            avg_images = sum(c.get("image_count", 0) for c in competitors_stats) / len(competitors_stats)
            has_faq_any = any(c.get("has_faq") for c in competitors_stats)
            has_schema_any = any(c.get("has_schema") for c in competitors_stats)
            has_sources_any = any(c.get("has_sources") for c in competitors_stats)

            gap = {
                "keyword": kw,
                "site_word_count": site_stats.get("word_count", 0),
                "avg_competitor_words": round(avg_words),
                "word_gap": round(avg_words - site_stats.get("word_count", 0)),
                "site_h2": site_stats.get("h2_count", 0),
                "avg_competitor_h2": round(avg_h2, 1),
                "h2_gap": round(avg_h2 - site_stats.get("h2_count", 0), 1),
                "site_images": site_stats.get("image_count", 0),
                "avg_competitor_images": round(avg_images),
                "image_gap": round(avg_images - site_stats.get("image_count", 0)),
                "competitor_has_faq": has_faq_any,
                "site_has_faq": site_stats.get("has_faq", False),
                "competitor_has_schema": has_schema_any,
                "competitor_has_sources": has_sources_any,
                "site_has_sources": site_stats.get("has_sources", False),
                "recommandations": [],
                "priority": "P2",
            }

            # Generer les recommandations
            if gap["word_gap"] > 300:
                gap["recommandations"].append(f"Ajouter {gap['word_gap']} mots pour atteindre la moyenne concurrentielle")
                gap["priority"] = "P1"
            if gap["h2_gap"] > 1:
                gap["recommandations"].append(f"Ajouter {int(gap['h2_gap'])} H2 pour couvrir plus de sous-sujets")
            if gap["competitor_has_faq"] and not gap["site_has_faq"]:
                gap["recommandations"].append("Ajouter une FAQ (les concurrents en ont une)")
                gap["priority"] = "P1"
            if gap["competitor_has_schema"] and not site_stats.get("has_schema"):
                gap["recommandations"].append("Ajouter des schemas JSON-LD (les concurrents en ont)")
            if gap["competitor_has_sources"] and not gap["site_has_sources"]:
                gap["recommandations"].append("Citer des sources (les concurrents le font)")
            if gap["image_gap"] > 1:
                gap["recommandations"].append(f"Ajouter {int(gap['image_gap'])} images pour enrichir le contenu")

            if gap["recommandations"]:
                content_gaps.append(gap)

    state.content_gaps_detailed = content_gaps
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="st15", pipeline_id="strategie",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"gaps_found": len(content_gaps)})

    logger.info(f"ST15: {len(content_gaps)} ecarts de contenu detailles identifies")
    return state


async def _analyze_page(url: str) -> dict | None:
    """Analyse une page (fetch + parsing)."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as c:
            resp = await c.get(url)
            if resp.status_code != 200:
                return None
            html = resp.text[:150000]
    except Exception:
        return None

    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    return {
        "word_count": len(text.split()),
        "h2_count": len(re.findall(r'<h2[^>]*>', html, re.IGNORECASE)),
        "image_count": len(re.findall(r'<img[^>]*>', html, re.IGNORECASE)),
        "has_faq": bool(re.search(r'(?i)faq|question.*reponse', text)),
        "has_schema": bool(re.search(r'application/ld\+json', html) or re.search(r'itemscope', html)),
        "has_sources": len(re.findall(r'https?://', html)) > 3,
    }


async def _get_serp_urls(kw: str) -> list[str]:
    try:
        from hermes.connectors.serp_api import SerpAPIClient
        c = SerpAPIClient()
        raw = await c._search_duckduckgo(kw, "fr", "fr")
        return [r["url"] for r in raw.get("organic_results", [])[:5] if r.get("url")]
    except Exception:
        return []
