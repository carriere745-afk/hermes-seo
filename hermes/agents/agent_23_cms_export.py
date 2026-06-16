"""Agent 23 — CMS Export.

Formate le contenu final pour export vers le CMS cible :
WordPress, WooCommerce, Shopify, Webflow ou HTML brut.
Pas d'appel LLM — formatage deterministe.
Conditionnellement obligatoire si target_cms est renseigne.
"""

from datetime import datetime
from html.parser import HTMLParser

from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import ExportData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


def _format_html(state: SessionState) -> ExportData:
    html = state.brouillon_html or ""
    seo = state.seo_data or {}
    schema = state.ld_json or {}
    meta_title = seo.get("title_optimise", state.keyword or "")
    meta_desc = seo.get("meta_description_optimise", "")
    ld = schema.get("ld_json", "")

    full = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{meta_title}</title>
<meta name="description" content="{meta_desc}">
<meta name="robots" content="index, follow">
<link rel="canonical" href="{state.site_url or ''}">
<script type="application/ld+json">
{ld}
</script>
</head>
<body>
<article>
{html}
</article>
</body>
</html>"""

    return ExportData(
        format="html",
        contenu_formate=full,
        metadata={"title": meta_title, "description": meta_desc, "canonical": state.site_url or ""},
        fichier=f"{state.keyword.replace(' ', '-') or 'article'}.html",
    )


def _format_wordpress(state: SessionState) -> ExportData:
    html = state.brouillon_html or ""
    seo = state.seo_data or {}
    schema = state.ld_json or {}
    entreprise = state.fiche_entreprise or {}

    # WP export : juste le HTML du contenu (titre + corps) + metadata
    title = seo.get("title_optimise", state.keyword or "")
    meta_desc = seo.get("meta_description_optimise", "")
    ld = schema.get("ld_json", "")

    wp_export = f"""<!-- wp:heading {{"level":1}} -->
<h1 class="wp-block-heading">{title}</h1>
<!-- /wp:heading -->

<!-- wp:html -->
{html if '<h1>' in html else html}
<!-- /wp:html -->
"""

    return ExportData(
        format="wordpress",
        contenu_formate=wp_export,
        metadata={
            "post_title": title,
            "post_status": "draft",
            "meta_description": meta_desc,
            "schema_ld_json": ld,
            "author": entreprise.get("nom", ""),
        },
        fichier=f"{state.keyword.replace(' ', '-') or 'article'}-wp.xml",
    )


def _format_woocommerce(state: SessionState) -> ExportData:
    html = state.brouillon_html or ""
    seo = state.seo_data or {}
    offre = state.offre_conversion_data or {}
    keyword = state.keyword or "produit"
    meta_desc = seo.get("meta_description_optimise", "")
    prix = offre.get("benefices", ["Prix sur demande"])[0]

    wc_export = f"""<!-- wp:woocommerce/product-details -->
<div class="woocommerce-product-details">
{html if html else f'<p>Description de {keyword}.</p>'}
</div>
<!-- /wp:woocommerce/product-details -->
"""

    return ExportData(
        format="woocommerce",
        contenu_formate=wc_export,
        metadata={
            "product_name": keyword,
            "product_description": meta_desc,
            "product_status": "draft",
        },
        fichier=f"product-{keyword.replace(' ', '-')}-wc.csv",
    )


def _format_shopify(state: SessionState) -> ExportData:
    html = state.brouillon_html or ""
    seo = state.seo_data or {}
    keyword = state.keyword or "produit"
    meta_desc = seo.get("meta_description_optimise", "")

    return ExportData(
        format="shopify",
        contenu_formate=html,
        metadata={
            "title": keyword,
            "description": meta_desc,
            "handle": keyword.lower().replace(" ", "-"),
            "status": "draft",
        },
        fichier=f"{keyword.replace(' ', '-')}-shopify.csv",
    )


def _format_webflow(state: SessionState) -> ExportData:
    html = state.brouillon_html or ""
    seo = state.seo_data or {}
    schema = state.ld_json or {}

    return ExportData(
        format="webflow",
        contenu_formate=html,
        metadata={
            "seo_title": seo.get("title_optimise", ""),
            "seo_description": seo.get("meta_description_optimise", ""),
            "schema_ld": schema.get("ld_json", ""),
        },
        fichier=f"{state.keyword.replace(' ', '-') or 'article'}-webflow.html",
    )


CMS_FORMATTERS = {
    "html": _format_html,
    "wordpress": _format_wordpress,
    "woocommerce": _format_woocommerce,
    "shopify": _format_shopify,
    "webflow": _format_webflow,
}


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_23"
    agent_name = "CMS Export"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"
    result.model_used = "library-only"
    result.tokens_input = 0
    result.tokens_output = 0
    result.cost_estimated = 0.0

    try:
        target = state.config.target_cms or "html"
        formatter = CMS_FORMATTERS.get(target, _format_html)
        export = formatter(state)

        state.export_data = export.model_dump()
        result.data = state.export_data
        result.status = AgentStatus.COMPLETED
    except Exception as e:
        export = ExportData(
            format="html",
            contenu_formate=state.brouillon_html or "",
            metadata={"error": str(e)},
            fichier="fallback.html",
        )
        state.export_data = export.model_dump()
        result.data = state.export_data
        result.status = AgentStatus.COMPLETED
        result.error_message = str(e)

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    log_agent_completed(agent_id, agent_name, result.duration_ms)
    state.last_completed_agent_id = agent_id
    return state
