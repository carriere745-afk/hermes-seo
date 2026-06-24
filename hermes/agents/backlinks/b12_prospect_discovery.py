"""B12 — Prospect Discovery Engine.

Decouvre des opportunites de backlinks par theme et secteur :
- Medias/blogs/podcasts/forums/annuaires pertinents
- Base sur le profil du site et les mots-cles
- Scoring de pertinence et d'autorite

Non skippable (MVP). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.backlinks import BacklinksState
from hermes.core.backlinks_db import insert_opportunities_batch
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b12")

# Base de prospects par secteur (simulee — en V2, scraping/API)
SECTOR_PROSPECTS = {
    "seo": [
        {"domain": "abondance.com", "type": "media_sectoriel", "dr": 65, "topical": 90},
        {"domain": "reakt.fr", "type": "blog", "dr": 50, "topical": 85},
        {"domain": "search-engine-journal.com", "type": "media_sectoriel", "dr": 85, "topical": 95},
        {"domain": "badsender.com", "type": "blog", "dr": 55, "topical": 75},
        {"domain": "les-dirigeants.fr", "type": "annuaire", "dr": 20, "topical": 30},
    ],
    "tech": [
        {"domain": "programmez.com", "type": "media_sectoriel", "dr": 60, "topical": 80},
        {"domain": "developpez.com", "type": "forum", "dr": 75, "topical": 85},
        {"domain": "journaldunet.com", "type": "media_national", "dr": 82, "topical": 70},
    ],
    "ecommerce": [
        {"domain": "ecommerce-nation.fr", "type": "media_sectoriel", "dr": 58, "topical": 85},
        {"domain": "siecledigital.fr", "type": "media_national", "dr": 72, "topical": 65},
        {"domain": "leptidigital.fr", "type": "blog", "dr": 48, "topical": 75},
    ],
    "formation": [
        {"domain": "cursus.edu", "type": "media_sectoriel", "dr": 55, "topical": 80},
        {"domain": "thot-cursus.com", "type": "blog", "dr": 50, "topical": 78},
        {"domain": "edtechactu.com", "type": "media_sectoriel", "dr": 42, "topical": 82},
    ],
    "sante": [
        {"domain": "doctissimo.fr", "type": "forum", "dr": 80, "topical": 90},
        {"domain": "sante-sur-le-net.com", "type": "media_sectoriel", "dr": 55, "topical": 85},
        {"domain": "pourquoidocteur.fr", "type": "media_sectoriel", "dr": 68, "topical": 88},
    ],
    "default": [
        {"domain": "blog-expert.fr", "type": "blog", "dr": 72, "topical": 75},
        {"domain": "media-pro.fr", "type": "media_sectoriel", "dr": 65, "topical": 70},
        {"domain": "podcast-business.fr", "type": "podcast", "dr": 45, "topical": 65},
        {"domain": "annuaire-pro.fr", "type": "annuaire", "dr": 30, "topical": 25},
        {"domain": "association-metier.fr", "type": "association", "dr": 35, "topical": 60},
    ],
}


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b12"
    state.phase = "analyse"

    discoveries: list[dict] = []
    opportunities: list[dict] = []

    # Selectionner les prospects par profil
    profile_prospects = SECTOR_PROSPECTS.get(state.profile, SECTOR_PROSPECTS["default"])

    # Ajouter des prospects generiques
    all_prospects = profile_prospects + SECTOR_PROSPECTS.get("default", [])[:3]

    # Filtrer ceux deja dans le profil
    existing_domains = {d.domain for d in state.referring_domains}
    new_prospects = [p for p in all_prospects if p["domain"] not in existing_domains]

    for p in new_prospects:
        # Score de pertinence
        relevance = int(p["dr"] * 0.4 + p["topical"] * 0.6)
        discoveries.append({
            "domain": p["domain"],
            "domain_type": p["type"],
            "domain_rating": p["dr"],
            "topical_score": p["topical"],
            "relevance_score": relevance,
            "opportunity_type": _map_type_to_opportunity(p["type"]),
            "description": f"Prospect {p['type']} dans le secteur — DR {p['dr']}, Topical {p['topical']}",
        })

    # Trier par pertinence
    discoveries.sort(key=lambda d: d["relevance_score"], reverse=True)

    # Convertir en opportunites
    for disc in discoveries[:30]:
        opportunities.append({
            "domain": disc["domain"],
            "domain_rating": disc["domain_rating"],
            "topical_score": disc["topical_score"],
            "opportunity_type": disc["opportunity_type"],
            "priority": "P1" if disc["relevance_score"] >= 70 else ("P2" if disc["relevance_score"] >= 50 else "P3"),
            "impact_score": disc["relevance_score"],
            "feasibility_score": 40,
            "cost_estime": 150.0 if disc["domain_rating"] > 60 else 80.0,
            "effort_estime": "2h",
            "source": "B12_discovery",
            "description": disc["description"],
            "keywords_cibles": state.keywords_cibles[:3] if state.keywords_cibles else [],
        })

    if opportunities:
        insert_opportunities_batch(opportunities)

    state.prospect_discoveries = discoveries
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="b12", pipeline_id="backlinks",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
    )

    logger.info(f"B12: {len(discoveries)} prospects decouverts — {len(opportunities)} opportunites")
    return state


def _map_type_to_opportunity(domain_type: str) -> str:
    mapping = {
        "media_national": "guest_post",
        "media_sectoriel": "guest_post",
        "blog": "guest_post",
        "annuaire": "annuaire",
        "forum": "forum",
        "podcast": "podcast",
        "association": "partenariat",
    }
    return mapping.get(domain_type, "guest_post")
