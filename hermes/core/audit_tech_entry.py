"""Point d'entree du Pipeline Audit Technique.

5 modes d'entree (identiques au Pipeline 2) :
  1. URL unique
  2. Liste d'URLs
  3. Sitemap XML (auto-detection + BFS)
  4. Crawl BFS depuis la homepage
  5. Import CSV

Ajoute le mode consentement propre au Pipeline 3.
"""

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from hermes.core.audit_entry import resolve_entry_urls
from hermes.models.audit_tech import TechAuditState

logger = logging.getLogger("hermes.audit_tech.entry")

# Profils client avec leurs poids de priorisation par defaut
CLIENT_PROFILES = {
    "ecommerce": {"impact_seo": 0.40, "impact_business": 0.50, "effort": 0.10, "conformite": 0.00},
    "blog": {"impact_seo": 0.60, "impact_business": 0.30, "effort": 0.10, "conformite": 0.00},
    "institutionnel": {"impact_seo": 0.30, "impact_business": 0.20, "effort": 0.20, "conformite": 0.30},
    "agence": {"impact_seo": 0.40, "impact_business": 0.30, "effort": 0.20, "conformite": 0.10},
    "saas": {"impact_seo": 0.35, "impact_business": 0.45, "effort": 0.15, "conformite": 0.05},
}


async def init_tech_audit(
    site_url: str = "",
    urls: Optional[list[str]] = None,
    mode: str = "standard",
    max_urls: int = 100,
    max_depth: int = 3,
    profile: str = "blog",
    consent_given: bool = False,
    respect_robots_txt: bool = True,
    rate_limit_rps: float = 2.0,
) -> TechAuditState:
    """Initialise un etat d'audit technique a partir d'une URL ou d'une liste.

    Args:
        site_url: URL racine du site
        urls: liste d'URLs pre-resolues (si deja connues)
        mode: fast/standard/premium/debug
        max_urls: nombre max d'URLs a crawler
        max_depth: profondeur max de crawl
        profile: ecommerce/blog/institutionnel/agence/saas
        consent_given: l'utilisateur a-t-il donne son consentement ?
        respect_robots_txt: respecter robots.txt ?
        rate_limit_rps: requetes par seconde max

    Returns: TechAuditState pret pour le workflow
    """
    if not site_url and not urls:
        raise ValueError("site_url ou urls requis")

    state = TechAuditState(
        site_url=site_url,
        mode=mode,
        max_urls=max_urls,
        max_depth=max_depth,
        profile=profile,
        consent_given=consent_given,
        respect_robots_txt=respect_robots_txt,
        rate_limit_rps=rate_limit_rps,
        urls=urls or [],
    )

    if state.site_url and not state.site_url.startswith("http"):
        state.site_url = f"https://{state.site_url}"

    parsed = urlparse(state.site_url)
    state.domain = parsed.netloc.lower().replace("www.", "")

    state.session_id = f"tech-{state.domain}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    state.status = "initialized"

    return state


async def resolve_tech_urls(
    mode: str,
    input_value: str,
    max_urls: int = 100,
    max_depth: int = 3,
) -> tuple[list[str], str, dict]:
    """Resout les URLs a auditer selon le mode d'entree.

    Reutilise resolve_entry_urls() du Pipeline 2.

    Returns: (urls, site_url, meta)
    """
    result = await resolve_entry_urls(
        mode=mode,
        input_value=input_value,
        max_urls=max_urls,
        max_depth=max_depth,
    )

    if not result["success"]:
        raise ValueError(result.get("error", "Resolution d'URLs echouee"))

    return result["urls"], result["site_url"], result.get("meta", {})
