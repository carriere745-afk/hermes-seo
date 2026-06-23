"""S04 — Monitoring Concurrent (enrichi).

Surveille les concurrents et les classifie pour evaluer la competitivite :
- Classification automatique : local / annuaire / marque nationale / media / forum / ecommerce
- Score de faisabilite DA : DA du site vs DA moyen du top 10 → opportunite
- Detection des concurrents faibles (annuaires, petits locaux) = opportunite
- Alerte si concurrent fort (marque nationale) entre dans le top 10

Skippable si aucun concurrent defini et detection auto infructueuse.
$0 — utilise TalorData + RankParse.
"""

import logging
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from hermes.models.serp_visibility import SerpVisibilityState, CompetitorEntry, AlertEntry

logger = logging.getLogger("hermes.serp.sv04")

# Patterns de classification des concurrents
COMPETITOR_TYPES = {
    "annuaire": {
        "patterns": ["pagesjaunes", "mappy", "annuaire", "yelp", "tripadvisor", "kompass",
                      "118000", "118218", "societe.com", "pappers", "infogreffe", "manageo",
                      "siret", "kompass.com", "cylex", "ouestfrance-emploi"],
        "threat_level": "low",
        "description": "Annuaire generaliste — faible menace SEO",
    },
    "local": {
        "patterns": [],  # Detecte par heuristique : domaine court, pas de patterns nationaux
        "threat_level": "low",
        "description": "Petit site local — faible menace SEO",
    },
    "marque_nationale": {
        "patterns": ["leboncoin", "amazon", "cdiscount", "fnac", "darty", "boulanger",
                      "leroymerlin", "castorama", "ikea", "decathlon", "carrefour",
                      "auchan", "leclerc", "lidl", "aldi", "but", "conforama",
                      "manomano", "sephora", "nocibe", "marionnaud",
                      "onet", "iss", "sodexo", "derichebourg", "elis"],
        "threat_level": "high",
        "description": "Marque nationale — forte menace SEO (autorite elevee)",
    },
    "media": {
        "patterns": ["lefigaro", "lemonde", "lesechos", "leparisien", "ouest-france",
                      "20minutes", "bfmtv", "franceinfo", "francetvinfo", "ladepeche"],
        "threat_level": "high",
        "description": "Media national — forte autorite de domaine",
    },
    "marketplace": {
        "patterns": ["etsy", "aliexpress", "ebay", "rakuten", "vinted", "backmarket"],
        "threat_level": "medium",
        "description": "Marketplace — concurrence moderee (contenu non specialiste)",
    },
    "forum": {
        "patterns": ["forum", "reddit.com", "quora.com", "communaute", "doctissimo"],
        "threat_level": "low",
        "description": "Forum / communaute — souvent non optimise SEO",
    },
    "gouvernement": {
        "patterns": [".gouv.fr", "service-public.fr", "data.gouv.fr"],
        "threat_level": "medium",
        "description": "Site gouvernemental — forte autorite de domaine, contenu non commercial",
    },
}


def _classify_competitor(domain: str) -> dict:
    """Classifie un concurrent selon son domaine."""
    domain_lower = domain.lower()
    for comp_type, info in COMPETITOR_TYPES.items():
        if comp_type == "local":
            continue  # Detecte separement
        for pattern in info["patterns"]:
            if pattern in domain_lower:
                return {
                    "type": comp_type,
                    "threat_level": info["threat_level"],
                    "description": info["description"],
                }

    # Heuristique "local" : domaine court (< 20 chars), .fr, pas de patterns connus
    if len(domain_lower) < 25 and (".fr" in domain_lower or domain_lower.count(".") <= 2):
        return {"type": "local", "threat_level": "low", "description": "Probablement un petit site local"}
    return {"type": "autre", "threat_level": "medium", "description": "Concurrent non classifie"}


def _compute_competitive_landscape(competitors: list[dict]) -> dict:
    """Analyse le paysage concurrentiel global et genere des insights."""
    types = Counter(c["classification"]["type"] for c in competitors if c.get("classification"))
    total = len(competitors) or 1
    low_threat = sum(1 for c in competitors if c.get("classification", {}).get("threat_level") == "low")
    high_threat = sum(1 for c in competitors if c.get("classification", {}).get("threat_level") == "high")

    # Generer des encouragements
    encouragements = []
    if low_threat >= total * 0.5:
        encouragements.append(
            f"🟢 Bonne nouvelle : {low_threat}/{total} concurrents sont des sites a faible menace SEO "
            f"(annuaires, petits locaux, forums). La barriere a l'entree est BASSE — "
            f"avec un contenu optimise, vous pouvez viser le top 3 en 2-4 mois."
        )
    if types.get("annuaire", 0) >= 2:
        encouragements.append(
            f"💡 {types['annuaire']} annuaires dans le top 10 — ces sites ne produisent pas de contenu unique. "
            f"Un article de fond avec FAQ, avis clients et schema LocalBusiness les depassera facilement."
        )
    if types.get("local", 0) >= 3:
        encouragements.append(
            f"🌟 {types['local']} petits sites locaux en top 10 — ils ont probablement un SEO basique. "
            f"Un contenu AEO/GEO bien structure vous donnera un avantage immediat."
        )
    if high_threat == 0:
        encouragements.append(
            f"🚀 Aucune marque nationale ni grand media dans le top 10. "
            f"Ce mot-cle est TRES accessible — c'est une opportunite a saisir rapidement."
        )
    if high_threat >= 2:
        encouragements.append(
            f"⚠️ {high_threat} concurrents a forte autorite (marques/medias) dans le top 10. "
            f"Concentrez-vous sur la longue traine et les variantes locales pour contourner leur dominance."
        )

    return {
        "total": total,
        "low_threat": low_threat,
        "high_threat": high_threat,
        "types_breakdown": dict(types),
        "encouragements": encouragements,
        "difficulty_assessment": (
            "facile" if high_threat == 0 else
            "moderee" if high_threat <= total * 0.3 else
            "difficile"
        ),
    }


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv04"
    if not state.keywords:
        return state

    # Auto-detecter les concurrents si pas definis
    if not state.competitors:
        state.competitors = await _auto_detect_competitors(state.keywords, state.domain)
        if not state.competitors:
            logger.info("S04: aucun concurrent detecte — skip")
            return state
        logger.info(f"S04: {len(state.competitors)} concurrents auto-detectes: {state.competitors[:5]}")

    # Classifier chaque concurrent
    classified = {}
    for comp in state.competitors:
        classified[comp] = _classify_competitor(comp)

    # Verifier DA du site pour le score de faisabilite
    site_da = 0
    try:
        from hermes.connectors.rankparse_connector import rankparse
        if rankparse.is_configured:
            da_data = await rankparse.get_domain_authority(state.domain)
            site_da = da_data.get("da", 0) if da_data else 0
    except Exception:
        pass

    # Collecter les positions concurrents
    competitor_positions = []
    competitor_das = []
    for competitor in state.competitors[:5]:
        # DA du concurrent
        comp_da = 0
        try:
            from hermes.connectors.rankparse_connector import rankparse
            if rankparse.is_configured:
                da_data = await rankparse.get_domain_authority(competitor)
                comp_da = da_data.get("da", 0) if da_data else 0
                competitor_das.append(comp_da)
        except Exception:
            pass

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
                        # Alerte si concurrent fort en top 3
                        cl = classified.get(competitor, {})
                        if i <= 2 and cl.get("threat_level") == "high":
                            state.alerts.append(AlertEntry(
                                type="concurrent_fort_top3",
                                keyword=kw,
                                priorite="P1",
                                date=datetime.now(),
                                note=f"{competitor} ({cl.get('type','inconnu')}) en position {i+1} — forte autorite"
                            ))
                        # Alerte plus legere si concurrent faible
                        elif i <= 2 and cl.get("threat_level") == "low":
                            state.alerts.append(AlertEntry(
                                type="concurrent_faible_top3",
                                keyword=kw,
                                priorite="P2",
                                date=datetime.now(),
                                note=f"{competitor} ({cl.get('type','annuaire/local')}) en top 3 — opportunite de depassement"
                            ))
            except Exception:
                continue

    state.competitor_positions = competitor_positions

    # Analyser le paysage concurrentiel
    competitors_classified = [{"domain": c, "classification": classified.get(c, {})} for c in state.competitors]
    landscape = _compute_competitive_landscape(competitors_classified)

    # Ajouter les encouragements comme alertes informatives
    for enc in landscape["encouragements"]:
        state.alerts.append(AlertEntry(
            type="opportunite_concurrentielle",
            priorite="info",
            date=datetime.now(),
            note=enc,
        ))

    # DA feasibility score
    avg_top_da = sum(competitor_das) / max(1, len(competitor_das))
    if site_da > 0 and avg_top_da > 0:
        try:
            from hermes.connectors.rankparse_connector import rankparse
            feasibility = rankparse.feasibility_score(site_da, avg_top_da)
            if feasibility:
                state.alerts.append(AlertEntry(
                    type="faisabilite_da",
                    priorite="info",
                    date=datetime.now(),
                    note=(
                        f"DA site: {site_da}/100 | DA moyen top 10: {avg_top_da}/100 | "
                        f"Faisabilite: {feasibility.get('score', '?')}% ({feasibility.get('label', '?')}). "
                        f"Contexte favorable — continuer le contenu de qualite."
                        if feasibility.get("score", 0) >= 70 else
                        f"Contexte concurrentiel — privilegier la longue traine et l'AEO/GEO."
                    ),
                ))
        except Exception:
            pass

    state.competitors = list(classified.keys())  # Mettre a jour avec classification

    logger.info(
        f"S04: {len(state.competitor_positions)} positions, "
        f"paysage: {landscape['difficulty_assessment']} "
        f"(low={landscape['low_threat']}, high={landscape['high_threat']}), "
        f"encouragements={len(landscape['encouragements'])}"
    )
    state.updated_at = datetime.now()
    return state


async def _auto_detect_competitors(keywords: list[str], site_domain: str = "", max_competitors: int = 5) -> list[str]:
    """Detecte automatiquement les concurrents via TalorData, en excluant le site lui-meme."""
    domains = Counter()
    try:
        from hermes.connectors.serp_api import SerpAPIClient
        client = SerpAPIClient(dry_run=False)

        for kw in keywords[:10]:
            try:
                serp = await client.search(kw, "fr", "fr")
                for result in serp.get("organic_results", [])[:10]:
                    domain = result.get("domain", "")
                    if domain and site_domain not in domain:
                        domains[domain] += 1
            except Exception:
                continue

        return [d for d, _ in domains.most_common(max_competitors + 3)][:max_competitors]
    except Exception:
        return []
