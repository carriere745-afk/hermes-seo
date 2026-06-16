"""Tests unitaires pour Agent 23 — CMS Export."""

import asyncio, pytest
from hermes.agents.agent_23_cms_export import run, CMS_FORMATTERS
from hermes.models.agent_data import ExportData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


def _session(target_cms="html", **kw):
    return SessionState(
        keyword="guide assurance vie",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, target_cms=target_cms),
        type_page="article",
        fiche_entreprise={"nom": "MonAssureur"},
        brouillon_html="<h1>Guide</h1><p>Contenu complet.</p>",
        seo_data={"title_optimise": "Guide Assurance Vie 2026", "meta_description_optimise": "Tout savoir."},
        ld_json={"ld_json": '{"@type":"Article"}'},
        site_url="https://example.fr",
        agent_results={"agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED)},
        **kw,
    )


# ─── 1. Entrée valide ────────────────────────────────────────────────

def test_run_html():
    result = asyncio.run(run(_session("html")))
    assert result.export_data["format"] == "html"
    assert "DOCTYPE" in result.export_data["contenu_formate"]
    assert result.export_data["fichier"].endswith(".html")
    assert result.agent_results["agent_23"].status == AgentStatus.COMPLETED


def test_run_wordpress():
    result = asyncio.run(run(_session("wordpress")))
    assert result.export_data["format"] == "wordpress"
    assert "wp:heading" in result.export_data["contenu_formate"]


def test_run_woocommerce():
    result = asyncio.run(run(_session("woocommerce")))
    assert result.export_data["format"] == "woocommerce"


def test_run_shopify():
    result = asyncio.run(run(_session("shopify")))
    assert result.export_data["format"] == "shopify"


def test_run_webflow():
    result = asyncio.run(run(_session("webflow")))
    assert result.export_data["format"] == "webflow"


def test_run_pydantic_valide():
    ExportData.model_validate(asyncio.run(run(_session())).export_data)


# ─── 2. Entrée invalide ───────────────────────────────────────────────

def test_run_sans_cms_defaut_html():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.export_data["format"] == "html"


def test_run_cms_inconnu_defaut_html():
    result = asyncio.run(run(_session("magento")))
    assert result.export_data["format"] == "html"


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_export_tous_les_champs():
    result = asyncio.run(run(_session()))
    for field in ("format", "contenu_formate", "metadata", "fichier"):
        assert field in result.export_data


def test_metadata_contenant_seo():
    result = asyncio.run(run(_session("html")))
    assert "title" in result.export_data["metadata"]


def test_resultat_stocke():
    result = asyncio.run(run(_session()))
    assert result.agent_results["agent_23"].data == result.export_data


def test_zero_cout():
    result = asyncio.run(run(_session()))
    assert result.agent_results["agent_23"].cost_estimated == 0.0


# ─── 4. Bibliothèque ──────────────────────────────────────────────────

def test_tous_les_formats_disponibles():
    for fmt in ("html", "wordpress", "woocommerce", "shopify", "webflow"):
        assert fmt in CMS_FORMATTERS


def test_tous_callables():
    for fn in CMS_FORMATTERS.values():
        assert callable(fn)
