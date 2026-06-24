"""B02 — Qualite & Scoring Domaines.

Score chaque domaine referent sur 5 dimensions :
- Domain Rating (DR) normalise 0-100
- Topical Score (pertinence thematique)
- Link Scarcity (rarete des liens sortants)
- Geo Relevance (pertinence geographique)
- Anchor Health (sante du profil d'ancre)

Non skippable. $0 — pas de LLM.
"""

import logging
import time
from collections import Counter
from datetime import datetime

from hermes.models.backlinks import BacklinksState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b02")

# Mots-cles thematiques par secteur (simplifie)
SECTOR_KEYWORDS = {
    "seo": ["seo", "referencement", "google", "serp", "backlink", "netlinking", "positionnement"],
    "tech": ["logiciel", "saas", "api", "cloud", "dev", "code", "application"],
    "ecommerce": ["boutique", "produit", "achat", "vente", "livraison", "panier", "promo"],
    "sante": ["sante", "medical", "patient", "traitement", "medecin", "hopital", "bien-etre"],
    "finance": ["finance", "banque", "credit", "investissement", "assurance", "epargne", "bourse"],
    "formation": ["formation", "cours", "apprendre", "certification", "diplome", "tutoriel"],
    "local": ["ville", "region", "departement", "mairie", "local", "proximite", "quartier"],
}


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b02"
    state.phase = "analyse"

    quality_scores: dict[str, float] = {}
    anchor_counts: Counter = Counter()
    total_anchors = 0

    for domain_entry in state.referring_domains:
        dom = domain_entry.domain
        dr = domain_entry.domain_rating

        # 1. DR score (0-100, deja normalise)
        dr_score = dr

        # 2. Topical Score — matching thematique basique
        topical = _compute_topical_score(dom, state)

        # 3. Link Scarcity — estimee via le nombre de backlinks
        n_bl = domain_entry.backlinks_count
        scarcity = max(0, 100 - n_bl * 5)  # Moins il y a de liens, plus c'est rare

        # 4. Geo Relevance
        geo = 80 if domain_entry.country == "FR" else (50 if domain_entry.country in ("BE", "CH", "LU") else 20)

        # 5. Score pondere final
        quality = (dr_score * 0.30 + topical * 0.25 + scarcity * 0.20 + geo * 0.15 + 50 * 0.10)
        quality_scores[dom] = round(min(100, max(0, quality)), 1)

        # Mettre a jour le domaine
        domain_entry.topical_score = round(topical, 1)
        domain_entry.link_scarcity = round(scarcity, 1)
        domain_entry.geo_relevance = round(geo, 1)

    # Analyser les ancres
    for bl in state.backlinks:
        anchor_text = bl.anchor_text.lower().strip()
        if anchor_text:
            anchor_counts[anchor_text] += 1
            total_anchors += 1

    # Analyser follow/nofollow
    dofollow_count = sum(1 for bl in state.backlinks if bl.is_dofollow)
    nofollow_count = len(state.backlinks) - dofollow_count
    total_bl = max(len(state.backlinks), 1)
    dofollow_ratio = dofollow_count / total_bl * 100
    nofollow_ratio = nofollow_count / total_bl * 100

    # Stocker le profil d'ancre
    anchor_types = {"brand": 0, "exact_match": 0, "partial_match": 0, "generic": 0, "url_naked": 0, "long_tail": 0}
    for bl in state.backlinks:
        at = _classify_anchor(bl.anchor_text, state.domain)
        bl.anchor_type = at
        anchor_types[at] = anchor_types.get(at, 0) + 1

    state.anchor_profile = {
        "current": {k: round(v / total_bl * 100, 1) for k, v in anchor_types.items()},
        "total_anchors": total_bl,
        "unique_anchors": len(anchor_counts),
        "dofollow_ratio": round(dofollow_ratio, 1),
        "nofollow_ratio": round(nofollow_ratio, 1),
        "dofollow_count": dofollow_count,
        "nofollow_count": nofollow_count,
        "follow_alert": "Risque penalite — profil trop artificiel" if dofollow_ratio > 95 and total_bl > 10 else (
            "Profil dofollow/nofollow equilibre" if 70 <= dofollow_ratio <= 90 else
            "Trop de nofollow — les liens n'apportent pas assez de jus SEO" if nofollow_ratio > 50 else "OK"
        ),
    }

    state.quality_scores = quality_scores
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="b02", pipeline_id="backlinks",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
    )

    avg_quality = sum(quality_scores.values()) / max(len(quality_scores), 1)
    logger.info(f"B02: {len(quality_scores)} domaines scores — qualite moyenne {avg_quality:.1f}/100")
    return state


def _compute_topical_score(domain: str, state: BacklinksState) -> float:
    """Score de pertinence thematique base sur le matching de mots-cles."""
    domain_lower = domain.lower()
    profile = state.profile or "blog"
    keywords = SECTOR_KEYWORDS.get(profile, SECTOR_KEYWORDS["seo"])
    matches = sum(1 for kw in keywords if kw in domain_lower)
    return min(100, matches / max(len(keywords), 1) * 100)


def _classify_anchor(anchor: str, domain: str) -> str:
    """Classifie le type d'ancre."""
    a = anchor.lower().strip()
    if not a or a in ("cliquez ici", "en savoir plus", "ici", "www"):
        return "generic"
    if domain.lower() in a:
        if a == domain.lower():
            return "brand"
        return "partial_match"
    if a.startswith("http"):
        return "url_naked"
    if domain.lower().replace(".fr", "").replace(".com", "") in a:
        return "partial_match"
    if len(a.split()) > 4:
        return "long_tail"
    return "exact_match"
