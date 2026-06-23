"""S08 — AEO / AI Overviews.

Analyse la presence du site dans les reponses des IA generatives :
- Google AI Overview (SGE) via TalorData/DataForSEO
- llms.txt presence et qualite
- AI Visibility Score 0-100

Skippable en mode fast ou standard.

$0 (+ ~$0.10/50 kw en premium via Playwright).
"""

import logging
from datetime import datetime

from hermes.models.serp_visibility import SerpVisibilityState, AIVisibilityEntry

logger = logging.getLogger("hermes.serp.sv08")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv08"
    if state.mode in ("fast", "standard") or not state.keywords:
        return state

    top_kw = state.keywords[:10]
    entries = []

    # 1. Google AI Overview via TalorData (stable)
    try:
        from hermes.connectors.serp_api import SerpAPIClient
        client = SerpAPIClient(dry_run=False)

        for kw in top_kw:
            try:
                serp = await client.search(kw, "fr", "fr")
                ai = serp.get("ai_overview", {})
                if ai.get("content"):
                    cited = state.domain in ai.get("content", "").lower()
                    entries.append(AIVisibilityEntry(
                        keyword=kw,
                        source_ia="SGE",
                        cited_url=state.site_url if cited else "",
                        citation_context=ai.get("content", "")[:200],
                        confidence="high",
                    ))
            except Exception:
                continue
    except Exception as e:
        logger.debug(f"S08: TalorData AI unavailable ({e})")

    state.ai_visibility = entries

    # 2. AI Visibility Score
    total = max(1, len(top_kw))
    cited_count = sum(1 for e in entries if e.cited_url)
    frequency_score = int(cited_count / total * 30)

    # Diversite des sources (pour l'instant SGE uniquement)
    sources = len(set(e.source_ia for e in entries))
    diversity_score = min(20, sources * 10)

    # Presence llms.txt (verifiee dans T22 / P3)
    llms_score = 20  # Default — sera enrichi par P3

    # Evolution (stub — pas d'historique)
    evolution_score = 15

    state.ai_visibility_score = frequency_score + diversity_score + llms_score + evolution_score

    logger.info(f"S08: {len(entries)} AI citations, visibility score={state.ai_visibility_score}")
    state.updated_at = datetime.now()
    return state
