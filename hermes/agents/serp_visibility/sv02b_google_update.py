"""S02b — Google Update Monitor.

Detecte les mises a jour algorithmiques de Google :
1. Heuristique interne : si > 20% des mots-cles varient simultanement → Core Update
2. Flux RSS (Google Search Central, Search Engine Roundtable, SEJ)

En cas de Core Update detecte : alerte P0 + suspension des alertes S07 pendant 7 jours.
Non skippable.

$0 — deterministe.
"""

import logging
from datetime import datetime, timedelta

from hermes.models.serp_visibility import SerpVisibilityState, AlertEntry

logger = logging.getLogger("hermes.serp.sv02b")

# Flux RSS a surveiller
RSS_FEEDS = [
    "https://developers.google.com/search/blog/atom.xml",
    "https://www.seroundtable.com/feed",
    "https://www.searchenginejournal.com/feed/",
]

# Mots-cles typiques des Core Updates
CORE_UPDATE_KEYWORDS = [
    "core update", "broad core algorithm", "google algorithm update",
    "google update", "ranking update", "search update",
    "spam update", "helpful content", "product review update",
]


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv02b"
    if not state.positions:
        return state

    # 1. Heuristique interne : % de mots-cles qui varient
    variations_count = len(state.variations) if state.variations else 0
    total_keywords = len(set(p.keyword for p in state.positions))
    if total_keywords == 0:
        return state

    variation_ratio = variations_count / total_keywords

    core_update_heuristic = variation_ratio > 0.20

    # 2. RSS check (optionnel)
    rss_detected = await _check_rss_for_updates()

    if core_update_heuristic or rss_detected:
        state.core_update_detected = True
        state.core_update_date = datetime.now()
        state.alerts.append(AlertEntry(
            type="core_update",
            priorite="P0",
            canal="Email",
            date=datetime.now(),
            note=(
                f"Probable Core Update detecte: {variation_ratio:.0%} des mots-cles varient simultanement"
                if core_update_heuristic else
                f"Core Update annonce via RSS"
            ),
        ))
        logger.warning(
            f"S02b: Core Update detected! Variation ratio={variation_ratio:.0%}, "
            f"RSS={'confirmed' if rss_detected else 'unconfirmed'}."
            " Alertes individuelles suspendues pendant 7 jours."
        )
    else:
        logger.info(f"S02b: no Core Update detected (ratio={variation_ratio:.1%})")

    state.updated_at = datetime.now()
    return state


async def _check_rss_for_updates() -> bool:
    """Verifie les flux RSS pour des annonces de Core Update."""
    try:
        import httpx
        from datetime import timezone

        async with httpx.AsyncClient(timeout=10) as client:
            for feed_url in RSS_FEEDS[:1]:  # Seulement Google pour eviter timeout
                try:
                    resp = await client.get(feed_url)
                    if resp.status_code != 200:
                        continue
                    text_lower = resp.text.lower()
                    if any(kw in text_lower for kw in CORE_UPDATE_KEYWORDS):
                        # Verifier la date de l'article
                        import re
                        dates = re.findall(r"<updated>([^<]+)</updated>", resp.text)
                        if dates:
                            pub_date = datetime.fromisoformat(dates[0].replace("Z", "+00:00"))
                            if (datetime.now(timezone.utc) - pub_date).days < 3:
                                return True
                except Exception:
                    continue
    except Exception:
        pass
    return False
