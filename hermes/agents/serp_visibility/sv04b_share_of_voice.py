"""S04b — Share of Voice.

Calcule la part de voix du site vs concurrents sur les mots-cles suivis.

Metriques :
- SOV Impressions : % des impressions totales du top 10
- SOV Clics : % des clics totaux du top 10
- Weighted Visibility : SOV pondere par le volume de recherche

Skippable en mode fast.

$0 — deterministe.
"""

import logging
from collections import defaultdict
from datetime import datetime

from hermes.models.serp_visibility import SerpVisibilityState, ShareOfVoiceEntry

logger = logging.getLogger("hermes.serp.sv04b")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv04b"
    if state.mode == "fast" or not state.positions:
        return state

    # Agreger par domaine
    domain_impressions: dict[str, float] = defaultdict(float)
    domain_clicks: dict[str, float] = defaultdict(float)
    domain_weighted: dict[str, float] = defaultdict(float)

    for pos in state.positions:
        domain = state.domain
        domain_impressions[domain] += pos.impressions
        domain_clicks[domain] += pos.clicks
        if pos.search_volume > 0:
            domain_weighted[domain] += pos.search_volume * (1 / max(1, pos.position))

    # Ajouter les concurrents
    for comp in state.competitor_positions:
        domain = comp.domain
        domain_impressions[domain] += 1  # Estimation conservative
        domain_clicks[domain] += 0.5
        for pos in state.positions:
            if pos.keyword == comp.keyword:
                domain_weighted[domain] += pos.search_volume * (1 / max(1, comp.position))

    total_imp = sum(domain_impressions.values()) or 1
    total_clicks = sum(domain_clicks.values()) or 1
    total_weighted = sum(domain_weighted.values()) or 1

    sov_entries = []
    for domain in domain_impressions:
        sov_entries.append(ShareOfVoiceEntry(
            domain=domain,
            date=datetime.now(),
            sov_impressions=round(domain_impressions[domain] / total_imp * 100, 2),
            sov_clicks=round(domain_clicks[domain] / total_clicks * 100, 2),
            weighted_visibility=round(domain_weighted[domain] / total_weighted * 100, 2),
        ))

    sov_entries.sort(key=lambda x: -x.weighted_visibility)
    state.share_of_voice = sov_entries

    # Score SOV
    our_sov = next((s for s in sov_entries if state.domain in s.domain), None)
    state.sov_score = round(our_sov.weighted_visibility) if our_sov else 0

    logger.info(f"S04b: SOV score={state.sov_score}, top domain={sov_entries[0].domain if sov_entries else 'none'}")
    state.updated_at = datetime.now()
    return state
