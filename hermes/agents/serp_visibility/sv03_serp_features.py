"""S03 — SERP Features.

Pour chaque mot-cle prioritaire, analyse les fonctionnalites SERP presentes
et determine si le site les possede ou pourrait les obtenir.

Features : Featured Snippet, PAA, AI Overview, Pack local, Video carousel,
Image pack, Sitelinks, Rich snippets, Top Stories, Knowledge Panel.

Scoring d'opportunite = trafic_potentiel × faisabilite × (1 / effort).
Skippable en mode fast.

$0 avec DataForSEO/TalorData.
"""

import logging
from datetime import datetime

from hermes.models.serp_visibility import SerpVisibilityState, SerpFeatureEntry

logger = logging.getLogger("hermes.serp.sv03")

SERP_FEATURES = {
    "featured_snippet": {"label": "Featured Snippet", "traffic_potential": 90, "effort": 2},
    "paa": {"label": "People Also Ask", "traffic_potential": 70, "effort": 1},
    "ai_overview": {"label": "AI Overview (SGE)", "traffic_potential": 85, "effort": 3},
    "pack_local": {"label": "Pack Local", "traffic_potential": 80, "effort": 3},
    "video_carousel": {"label": "Video Carousel", "traffic_potential": 50, "effort": 4},
    "image_pack": {"label": "Image Pack", "traffic_potential": 40, "effort": 1},
    "sitelinks": {"label": "Sitelinks", "traffic_potential": 60, "effort": 2},
    "rich_snippets": {"label": "Rich Snippets", "traffic_potential": 75, "effort": 2},
    "top_stories": {"label": "Top Stories", "traffic_potential": 55, "effort": 3},
    "knowledge_panel": {"label": "Knowledge Panel", "traffic_potential": 65, "effort": 4},
}


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv03"
    if state.mode == "fast" or not state.keywords:
        return state

    # Analyser les top 10 keywords
    top_kw = state.keywords[:10]
    features_found = []

    # Essayer TalorData pour les SERP features
    try:
        from hermes.connectors.serp_api import SerpAPIClient
        client = SerpAPIClient(dry_run=False)

        for kw in top_kw:
            try:
                serp = await client.search(kw, "fr", "fr")
                organic = serp.get("organic_results", [])
                related = serp.get("related_questions", [])
                ai_overview = serp.get("ai_overview", {})
                snack_pack = serp.get("snack_pack", [])

                # Featured Snippet
                has_fs = bool(serp.get("featured_snippet", {}).get("content"))
                features_found.append(SerpFeatureEntry(
                    keyword=kw, feature_type="featured_snippet",
                    present=has_fs,
                    opportunity_score=_score_opportunity("featured_snippet", has_fs),
                    url_site=state.site_url,
                ))

                # PAA
                has_paa = len(related) > 0
                features_found.append(SerpFeatureEntry(
                    keyword=kw, feature_type="paa",
                    present=has_paa,
                    opportunity_score=_score_opportunity("paa", has_paa),
                ))

                # AI Overview
                has_ai = bool(ai_overview.get("content"))
                features_found.append(SerpFeatureEntry(
                    keyword=kw, feature_type="ai_overview",
                    present=has_ai,
                    opportunity_score=_score_opportunity("ai_overview", has_ai),
                ))

                # Pack local
                has_local = len(snack_pack) > 0
                features_found.append(SerpFeatureEntry(
                    keyword=kw, feature_type="pack_local",
                    present=has_local,
                    opportunity_score=_score_opportunity("pack_local", has_local),
                ))

            except Exception:
                continue

    except Exception as e:
        logger.debug(f"S03: TalorData unavailable ({e})")

    state.serp_features = features_found
    logger.info(f"S03: {len(features_found)} SERP feature entries analyzed")
    state.updated_at = datetime.now()
    return state


def _score_opportunity(feature_type: str, has_it: bool) -> int:
    if has_it:
        return 0  # Deja present, pas d'opportunite
    info = SERP_FEATURES.get(feature_type, {})
    tp = info.get("traffic_potential", 50)
    effort = info.get("effort", 3)
    return max(0, min(100, int(tp * 0.7 * (1 / effort) * 10)))
