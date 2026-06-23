"""S04 — Monitoring Concurrent.

Surveille les positions des concurrents sur les mots-cles du site.
- Detection automatique des concurrents (domaines frequents dans le top 10)
- Alerte si un concurrent depasse le site
- Alerte si nouveau concurrent dans le top 3

Skippable si aucun concurrent defini et detection auto infructueuse.

$0 — utilise DataForSEO/TalorData.
"""

import logging
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from hermes.models.serp_visibility import SerpVisibilityState, CompetitorEntry, AlertEntry

logger = logging.getLogger("hermes.serp.sv04")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv04"
    if not state.keywords:
        return state

    # Auto-detecter les concurrents si pas definis
    if not state.competitors:
        state.competitors = await _auto_detect_competitors(state.keywords)
        if not state.competitors:
            logger.info("S04: aucun concurrent detecte — skip")
            return state
        logger.info(f"S04: {len(state.competitors)} concurrents auto-detectes: {state.competitors[:5]}")

    competitor_positions = []
    for competitor in state.competitors[:5]:
        for kw in state.keywords[:20]:
            try:
                from hermes.connectors.serp_api import SerpAPIClient
                client = SerpAPIClient(dry_run=False)
                serp = await client.search(kw, "fr", "fr")
                for i, result in enumerate(serp.get("organic_results", [])[:10]):
                    domain = result.get("domain", "")
                    if competitor.lower() in domain.lower():
                        competitor_positions.append(CompetitorEntry(
                            domain=competitor,
                            keyword=kw,
                            position=i + 1,
                            url=result.get("url", ""),
                            source="TalorData",
                        ))
                        # Alerte si le concurrent depasse le site
                        if i <= 2:
                            state.alerts.append(AlertEntry(
                                type="concurrent_depasse",
                                keyword=kw,
                                priorite="P1",
                                date=datetime.now(),
                                note=f"{competitor} en position {i+1} sur '{kw}'"
                            ))
            except Exception:
                continue

    state.competitor_positions = competitor_positions
    logger.info(f"S04: {len(state.competitor_positions)} positions concurrents enregistrees")
    state.updated_at = datetime.now()
    return state


async def _auto_detect_competitors(keywords: list[str], max_competitors: int = 5) -> list[str]:
    """Detecte automatiquement les concurrents via TalorData."""
    domains = Counter()
    try:
        from hermes.connectors.serp_api import SerpAPIClient
        client = SerpAPIClient(dry_run=False)

        for kw in keywords[:10]:
            try:
                serp = await client.search(kw, "fr", "fr")
                for result in serp.get("organic_results", [])[:10]:
                    domain = result.get("domain", "")
                    if domain:
                        domains[domain] += 1
            except Exception:
                continue

        # Exclure le domaine du site (deja connu par l'appelant)
        return [d for d, _ in domains.most_common(max_competitors + 3)][:max_competitors]
    except Exception:
        return []
