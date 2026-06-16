"""Agent 21 — Schema.org avance.

Genere le JSON-LD adapte au type de page : Article, Product, FAQPage,
LocalBusiness, NewsArticle, etc. Type-aware avec bibliotheque de schemas.
"""

import json
from datetime import datetime, date

from hermes.models.agent_data import SchemaData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState
from hermes.core.logging import log_agent_start, log_agent_completed


SCHEMA_TEMPLATES: dict[str, callable] = {}


def _schema_article(state: SessionState) -> dict:
    entreprise = state.fiche_entreprise or {}
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": state.seo_data.get("title_optimise", state.keyword or "Article"),
        "description": state.seo_data.get("meta_description_optimise", ""),
        "author": {
            "@type": "Organization",
            "name": entreprise.get("nom", "Auteur"),
        },
        "publisher": {
            "@type": "Organization",
            "name": entreprise.get("nom", "Editeur"),
            "url": state.site_url or "",
        },
        "datePublished": state.created_at.date().isoformat() if state.created_at else date.today().isoformat(),
        "dateModified": date.today().isoformat(),
        "mainEntityOfPage": {"@type": "WebPage", "@id": state.site_url or ""},
    }


def _schema_pilier(state: SessionState) -> dict:
    schema = _schema_article(state)
    schema["@type"] = "Article"
    schema["articleSection"] = state.keyword or ""
    schema["wordCount"] = len(state.brouillon_html or "") // 5
    return schema


def _schema_fiche_produit(state: SessionState) -> dict:
    entreprise = state.fiche_entreprise or {}
    offre = state.offre_conversion_data or {}
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": state.keyword or "Produit",
        "description": state.seo_data.get("meta_description_optimise", ""),
        "brand": {"@type": "Brand", "name": entreprise.get("nom", "Marque")},
        "offers": {
            "@type": "Offer",
            "availability": "https://schema.org/InStock",
            "priceCurrency": "EUR",
        },
        "review": {
            "@type": "Review",
            "reviewBody": offre.get("preuves", [""])[0] if offre.get("preuves") else "",
        },
    }


def _schema_faq(state: SessionState) -> dict:
    aeo = state.aeo_blocks or {}
    faq = aeo.get("faq", [])
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": q.get("question", ""),
                "acceptedAnswer": {"@type": "Answer", "text": q.get("reponse", "")},
            }
            for q in faq[:10]
        ],
    }


def _schema_service_local(state: SessionState) -> dict:
    entreprise = state.fiche_entreprise or {}
    return {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": entreprise.get("nom", "Entreprise"),
        "description": state.seo_data.get("meta_description_optimise", ""),
        "url": state.site_url or "",
        "telephone": "(a completer)",
        "address": {"@type": "PostalAddress", "addressLocality": "(a completer)"},
        "openingHoursSpecification": {
            "@type": "OpeningHoursSpecification",
            "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            "opens": "09:00",
            "closes": "18:00",
        },
    }


def _schema_news(state: SessionState) -> dict:
    schema = _schema_article(state)
    schema["@type"] = "NewsArticle"
    return schema


def _schema_comparatif(state: SessionState) -> dict:
    schema = _schema_article(state)
    schema["@type"] = "Article"
    schema["articleSection"] = "Comparatif"
    return schema


def _schema_landing(state: SessionState) -> dict:
    entreprise = state.fiche_entreprise or {}
    offre = state.offre_conversion_data or {}
    return {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": state.keyword or "Page",
        "description": state.seo_data.get("meta_description_optimise", ""),
        "provider": {"@type": "Organization", "name": entreprise.get("nom", "")},
        "offers": {"@type": "Offer", "name": offre.get("cta_principal", "")},
    }


SCHEMA_TEMPLATES = {
    "article": _schema_article,
    "pilier": _schema_pilier,
    "fiche_produit": _schema_fiche_produit,
    "faq": _schema_faq,
    "service_local": _schema_service_local,
    "comparatif": _schema_comparatif,
    "landing": _schema_landing,
    "news": _schema_news,
    "glossaire": _schema_article,
    "temoignage": _schema_article,
}


def _generate_schema(state: SessionState) -> SchemaData:
    type_page = state.type_page or "article"
    fn = SCHEMA_TEMPLATES.get(type_page, _schema_article)
    schema = fn(state)

    ld_json = json.dumps(schema, indent=2, ensure_ascii=False)
    schema_type = schema.get("@type", "Article")

    # Validation basique
    errors: list[str] = []
    if not schema.get("name") and not schema.get("headline"):
        errors.append("Pas de champ name/headline")
    if not schema.get("url") and not schema.get("mainEntityOfPage"):
        errors.append("Pas d'URL dans le schema")

    return SchemaData(ld_json=ld_json, type_schema=schema_type, validation_errors=errors)


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_21"
    agent_name = "Schema.org"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"
    result.model_used = "library-only"  # Pas de LLM, bibliotheque deterministe
    result.tokens_input = 0
    result.tokens_output = 0
    result.cost_estimated = 0.0

    try:
        schema = _generate_schema(state)
        state.ld_json = schema.model_dump()
        result.data = state.ld_json
        result.status = AgentStatus.COMPLETED
    except Exception as e:
        schema = SchemaData(
            ld_json="{}",
            type_schema="Article",
            validation_errors=[f"Erreur generation schema: {e}"],
        )
        state.ld_json = schema.model_dump()
        result.data = state.ld_json
        result.status = AgentStatus.COMPLETED
        result.error_message = str(e)

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    log_agent_completed(agent_id, agent_name, result.duration_ms,
                        tokens_input=0, tokens_output=0,
                        cost_estimated=0.0, prompt_version="v1",
                        model_used="library-only")
    state.last_completed_agent_id = agent_id
    return state
