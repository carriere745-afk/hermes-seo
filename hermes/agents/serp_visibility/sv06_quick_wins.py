"""S06 — Quick Wins.

Identifie les pages en position 4-15 avec volume de recherche significatif.
Ce sont les pages les plus proches du top 3 qui necessitent le moins d'effort.

Business Score = volume × taux_conversion × marge_estimee.
Non skippable.

$0 — deterministe.
"""

import logging
from datetime import datetime

from hermes.models.serp_visibility import SerpVisibilityState, QuickWin

logger = logging.getLogger("hermes.serp.sv06")

# Taux de conversion estime par type de page
CONVERSION_RATES = {
    "produit": 0.03, "product": 0.03,
    "service": 0.05,
    "article": 0.005, "blog": 0.005,
    "landing": 0.04, "lp": 0.04,
    "categorie": 0.01, "category": 0.01,
}
DEFAULT_CONVERSION_RATE = 0.01

# Marge estimee par type
MARGIN_RATES = {
    "produit": 0.30, "product": 0.30,
    "service": 0.50,
    "article": 0.10, "blog": 0.10,
    "landing": 0.40, "lp": 0.40,
}
DEFAULT_MARGIN = 0.20


def _get_page_type(url: str) -> str:
    import re
    path = url.lower()
    if re.search(r"/\d+-[\w-]+\.html?$", path):
        return "produit"
    if any(w in path for w in ("/blog/", "/article/", "/actualite/", "/news/", "/post/")):
        return "article"
    if any(w in path for w in ("/service/", "/prestation/", "/offre/")):
        return "service"
    if any(w in path for w in ("/landing/", "/lp/", "/promo/")):
        return "landing"
    if any(w in path for w in ("/categorie/", "/category/", "/collection/")):
        return "categorie"
    return "article"


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv06"
    if not state.positions:
        return state

    quick_wins = []
    for pos in state.positions:
        if not (4 <= pos.position <= 15):
            continue
        if pos.search_volume < 100:
            continue

        page_type = _get_page_type(pos.url)
        conv = CONVERSION_RATES.get(page_type, DEFAULT_CONVERSION_RATE)
        margin = MARGIN_RATES.get(page_type, DEFAULT_MARGIN)
        business_score = pos.search_volume * conv * margin

        # Action recommandee
        action = _recommend_action(pos.position, page_type)

        quick_wins.append(QuickWin(
            url=pos.url,
            keyword=pos.keyword,
            position=pos.position,
            search_volume=pos.search_volume,
            impressions_28j=pos.impressions,
            ctr_actuel=pos.ctr,
            business_score=round(business_score, 2),
            trend="stable",
            action_recommandee=action["description"],
            pipeline_cible=action["pipeline"],
            priorite="P1" if pos.position <= 10 else "P2",
        ))

    # Trier par business score decroissant
    quick_wins.sort(key=lambda w: -w.business_score)
    state.quick_wins = quick_wins[:30]

    logger.info(f"S06: {len(state.quick_wins)} quick wins, top business_score={quick_wins[0].business_score if quick_wins else 0}")
    state.updated_at = datetime.now()
    return state


def _recommend_action(position: int, page_type: str) -> dict:
    actions = {
        (4, 7): {"description": "Optimiser title/meta + schema", "pipeline": "P1"},
        (8, 12): {"description": "Enrichir contenu (FAQ, sources, entites)", "pipeline": "P1"},
        (13, 15): {"description": "Renforcer maillage interne + contenu", "pipeline": "P6"},
    }
    for (lo, hi), action in actions.items():
        if lo <= position <= hi:
            return action
    return {"description": "Enrichir contenu (P1) ou renforcer maillage (P6)", "pipeline": "P1"}
