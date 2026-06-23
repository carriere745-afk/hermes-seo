"""S05 — Gap Content SERP.

Pour les pages en position 4-20, analyse les ecarts avec le top 3.
Produit une liste de gaps actionnables transmise au Pipeline Editorial (P1).

Gaps : longueur contenu, PAA non couvertes, entites, sources, features.
LLM Haiku pour synthetiser les recommandations.

$0 (+ ~$0.005/page avec Haiku en premium).
"""

import logging
from datetime import datetime

from hermes.models.serp_visibility import SerpVisibilityState

logger = logging.getLogger("hermes.serp.sv05")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv05"
    if state.mode == "fast":
        return state

    # Selectionner les pages en position 4-20 avec le plus de potentiel
    candidates = [p for p in state.positions if 4 <= p.position <= 20 and p.search_volume > 100]
    if not candidates:
        logger.info("S05: pas de candidats pour le gap content")
        return state

    gaps = []
    for pos in candidates[:5]:
        try:
            from hermes.connectors.serp_api import SerpAPIClient
            client = SerpAPIClient(dry_run=False)
            serp = await client.search(pos.keyword, "fr", "fr")
            top3 = serp.get("organic_results", [])[:3]

            if not top3:
                continue

            gap = {
                "keyword": pos.keyword,
                "url": pos.url,
                "position": pos.position,
                "search_volume": pos.search_volume,
                "top3_urls": [r.get("url", "") for r in top3],
                "gaps": _analyze_gaps(serp, pos),
            }

            # Enrichir avec Haiku en mode premium
            if state.mode == "premium":
                gap["recommendation"] = await _enrich_gap_with_llm(gap)

            gaps.append(gap)
        except Exception as e:
            logger.debug(f"S05: gap analysis failed for {pos.keyword} ({e})")

    state.content_gaps = gaps
    logger.info(f"S05: {len(gaps)} content gaps analyzed")
    state.updated_at = datetime.now()
    return state


def _analyze_gaps(serp: dict, pos) -> list[str]:
    """Analyse les ecarts entre la page et le top 3."""
    gaps = []

    # PAA non couvertes
    related = serp.get("related_questions", [])
    if related:
        gaps.append(f"{len(related)} questions PAA a couvrir (FAQ)")

    # AI Overview
    ai = serp.get("ai_overview", {})
    if ai.get("content"):
        gaps.append("AI Overview presente — renforcer entites et sources pour y apparaitre")

    # Featured snippet
    fs = serp.get("featured_snippet", {})
    if fs.get("content"):
        gaps.append("Featured Snippet present — reformuler la reponse en 40-60 mots")

    # Longueur de contenu (estimation via le nombre de resultats)
    top3_count = len(serp.get("organic_results", []))
    if top3_count < 10:
        gaps.append("SERP peu competitive — opportunite de ranking")

    if not gaps:
        gaps.append("Ajouter contenu substantiel (FAQ, sources, statistiques)")

    return gaps


async def _enrich_gap_with_llm(gap: dict) -> str:
    """Enrichit les recommandations via Haiku."""
    try:
        from hermes.core.llm import call_llm
        prompt = (
            f"Keyword: {gap['keyword']} (volume: {gap['search_volume']}/mois)\n"
            f"Position actuelle: {gap['position']}\n"
            f"Gaps detectes: {', '.join(gap['gaps'])}\n\n"
            "En 1 phrase, quelle action concrete recommander pour progresser dans le top 3 ?"
        )
        return await call_llm(prompt, model="haiku", max_tokens=100, temperature=0.3) or ""
    except Exception:
        return ""
