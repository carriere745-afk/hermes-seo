"""T09 — Validation Schema.org.

Valide les donnees structurees (JSON-LD, microdata) :
- Detection des types Schema.org presents
- Validation via schorg (Pydantic models)
- Verification de la conformite avec le type de page
- Detection des champs obligatoires manquants
- Recommandations de schemas manquants par type de page

$0 — pas de LLM. Utilise schorg (oss, Pydantic).
"""

import json
import logging
import re
from datetime import datetime
from urllib.parse import urlparse

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt09")

# Mapping type de page → Schema.org recommande
RECOMMENDED_SCHEMAS = {
    "accueil": ["WebSite", "Organization"],
    "article": ["Article", "BreadcrumbList"],
    "produit": ["Product", "BreadcrumbList", "Organization"],
    "categorie": ["ItemList", "BreadcrumbList"],
    "service": ["Service", "Organization", "BreadcrumbList"],
    "faq": ["FAQPage", "BreadcrumbList"],
    "legale": [],
    "autre": ["BreadcrumbList"],
}

# Champs obligatoires par type Schema.org (simplifies)
REQUIRED_FIELDS = {
    "Article": ["headline", "datePublished"],
    "Product": ["name"],
    "FAQPage": ["mainEntity"],
    "Organization": ["name"],
    "LocalBusiness": ["name", "address"],
    "BreadcrumbList": ["itemListElement"],
    "WebSite": ["name", "url"],
    "Service": ["name", "provider"],
}


def _get_page_type(url: str) -> str:
    """Determine le type de page."""
    path = urlparse(url).path.lower()
    if path in ("/", ""):
        return "accueil"
    if re.search(r"/\d+-[\w-]+\.html?$", path):
        return "produit"
    if any(w in path for w in ("/blog/", "/article/", "/actualite/", "/news/", "/post/", "/module-blog")):
        return "article"
    if any(w in path for w in ("/produit/", "/product/")):
        return "produit"
    if any(w in path for w in ("/categorie/", "/category/", "/collection/")):
        return "categorie"
    if any(w in path for w in ("/service/", "/prestation/", "/offre/")):
        return "service"
    if any(w in path for w in ("/faq/", "/questions/", "/glossaire/")):
        return "faq"
    if any(w in path for w in ("/cgu/", "/cgv/", "/mentions/", "/privacy/", "/contact/", "/login", "/cart", "/checkout", "/mon-compte")):
        return "legale"
    return "autre"


def _validate_json_ld_types(json_ld_types: list[str]) -> dict:
    """Valide les types JSON-LD via schorg.

    Returns: {"errors": [str], "warnings": [str], "valid_types": [str]}
    """
    result = {"errors": [], "warnings": [], "valid_types": []}

    for schema_type in json_ld_types:
        try:
            # Verifier si le type est supporte par schorg
            from schorg import (
                Article, Product, FAQPage, Organization,
                LocalBusiness, BreadcrumbList, WebSite, Service,
                NewsArticle, ItemList, Event, Recipe,
            )
            supported = {
                "Article": Article, "Product": Product, "FAQPage": FAQPage,
                "Organization": Organization, "LocalBusiness": LocalBusiness,
                "BreadcrumbList": BreadcrumbList, "WebSite": WebSite,
                "Service": Service, "NewsArticle": NewsArticle,
                "ItemList": ItemList, "Event": Event, "Recipe": Recipe,
            }

            if schema_type in supported:
                result["valid_types"].append(schema_type)

                # Verifier les champs obligatoires
                required = REQUIRED_FIELDS.get(schema_type, [])
                if required:
                    result["warnings"].append(
                        f"{schema_type}: champs recommandes: {', '.join(required)}"
                    )
            else:
                result["warnings"].append(
                    f"Type '{schema_type}' non reconnu par le validateur Schema.org"
                )

        except ImportError:
            result["warnings"].append("schorg non disponible — validation simplifiee")
            break
        except Exception as e:
            result["errors"].append(f"Erreur validation {schema_type}: {e}")

    return result


async def run(state: TechAuditState) -> TechAuditState:
    """Valide les schemas des pages auditees."""
    state.current_agent = "tt09"

    if not state.crawled_pages:
        logger.warning("T09: aucune page — skip")
        return state

    pages_to_audit = [p for p in state.crawled_pages if p.status_code == 200 and not p.fetch_error]
    logger.info(f"T09: validating schemas for {len(pages_to_audit)} pages")

    issue_counter = len(state.issues)
    pages_with_schema = 0
    pages_missing_recommended = 0

    for page in pages_to_audit:
        page_type = _get_page_type(page.url)

        # 1. Validation des schemas existants
        if page.json_ld_types:
            pages_with_schema += 1
            validation = _validate_json_ld_types(page.json_ld_types)

            for err in validation.get("errors", []):
                issue_counter += 1
                state.issues.append(TechIssue(
                    id=f"P-{issue_counter:03d}",
                    category="schema",
                    description=f"Erreur schema.org : {err}",
                    url=page.url,
                    observed=f"json_ld_types: {page.json_ld_types}",
                    rule="schema.org valide",
                    confidence="high",
                    source_agent="T09",
                    severity="high",
                    impact_business="Medium",
                    gain_potentiel="Medium",
                    effort="Corriger le JSON-LD",
                    priority="P2",
                ))

            for warn in validation.get("warnings", [])[:3]:
                if "non reconnu" not in warn and "non disponible" not in warn:
                    issue_counter += 1
                    state.issues.append(TechIssue(
                        id=f"P-{issue_counter:03d}",
                        category="schema",
                        description=warn,
                        url=page.url,
                        observed=f"type: {page.json_ld_types}",
                        rule="schema.org complet",
                        confidence="medium",
                        source_agent="T09",
                        severity="low",
                        impact_business="Low",
                        gain_potentiel="Medium",
                        effort="Ajouter les champs recommandes au schema",
                        priority="P3",
                    ))

        # 2. Schemas recommandes manquants
        recommended = RECOMMENDED_SCHEMAS.get(page_type, ["BreadcrumbList"])
        if recommended:
            missing = [r for r in recommended if r not in page.json_ld_types]
            if missing and page_type != "legale":
                pages_missing_recommended += 1
                issue_counter += 1
                state.issues.append(TechIssue(
                    id=f"P-{issue_counter:03d}",
                    category="schema",
                    description=f"Schema(s) recommande(s) manquant(s) pour une page de type '{page_type}' : {', '.join(missing)}",
                    url=page.url,
                    observed=f"json_ld_types presents: {page.json_ld_types or 'aucun'}",
                    rule=f"Schemas recommandes pour '{page_type}': {recommended}",
                    confidence="medium",
                    source_agent="T09",
                    severity="medium",
                    impact_business="Medium",
                    gain_potentiel="Medium",
                    effort=f"Ajouter les schemas : {', '.join(missing)}",
                    priority="P3",
                    cms_location=(
                        "WordPress → Yoast/RankMath → Schema → Activer le type"
                        if state.cms_detected == "WordPress" else
                        "PrestaShop → Module SEO → Schema"
                        if state.cms_detected == "PrestaShop" else
                        None
                    ),
                ))

        # 3. JSON-LD invalide (flag du crawler)
        if not page.json_ld_valid and page.microdata_present:
            # Le crawler a detecte du microdata sans JSON-LD
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="schema",
                description="Microdata presents mais pas de JSON-LD valide — Google recommande JSON-LD",
                url=page.url,
                observed="microdata: true, json_ld_valid: false",
                rule="JSON-LD recommande par Google",
                confidence="high",
                source_agent="T09",
                severity="low",
                impact_business="Low",
                gain_potentiel="Medium",
                effort="Convertir le microdata en JSON-LD",
                priority="P3",
            ))

    logger.info(f"T09: {pages_with_schema} pages with schema, {pages_missing_recommended} missing recommended")

    # Scoring
    if pages_to_audit:
        total = len(pages_to_audit)
        with_schema = pages_with_schema
        # 50% du score = presence de schema, 50% = pas de schemas manquants
        score = int((with_schema / total * 50) + ((total - pages_missing_recommended) / total * 50))
        state.scores.structured_data.score = score
        state.scores.structured_data.confidence = "high"

    state.updated_at = datetime.now()
    return state
