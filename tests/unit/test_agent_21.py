"""Tests unitaires pour Agent 21 — Schema.org."""

import json, asyncio, pytest

from hermes.agents.agent_21_schema_org import (
    _generate_schema, SCHEMA_TEMPLATES, run,
)
from hermes.models.agent_data import SchemaData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


def _session(type_page="article", keyword="test", **kw):
    return SessionState(
        keyword=keyword, type_page=type_page,
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        fiche_entreprise={"nom": "TestCorp"},
        seo_data={"title_optimise": f"Guide {keyword}", "meta_description_optimise": "Description."},
        aeo_blocks={"faq": [{"question": "Q1?", "reponse": "R1."}]},
        offre_conversion_data={"cta_principal": "Essayez"},
        brouillon_html="<h1>Test</h1><p>" + "x" * 200,
        site_url="https://test.fr",
        **kw,
    )


# ─── 1. Entrée valide ────────────────────────────────────────────────

def test_run_article():
    result = asyncio.run(run(_session("article")))
    assert result.ld_json is not None
    schema = json.loads(result.ld_json["ld_json"])
    assert schema["@type"] == "Article"
    assert result.agent_results["agent_21"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide():
    SchemaData.model_validate(asyncio.run(run(_session())).ld_json)


# ─── 2. Tous les types de page ────────────────────────────────────────

@pytest.mark.parametrize("type_page,expected_type", [
    ("article", "Article"), ("pilier", "Article"), ("fiche_produit", "Product"),
    ("faq", "FAQPage"), ("service_local", "LocalBusiness"), ("comparatif", "Article"),
    ("landing", "WebPage"), ("news", "NewsArticle"), ("glossaire", "Article"),
    ("temoignage", "Article"),
])
def test_schema_type_correct(type_page, expected_type):
    result = asyncio.run(run(_session(type_page)))
    schema = json.loads(result.ld_json["ld_json"])
    assert schema["@type"] == expected_type


def test_faq_a_main_entity():
    result = asyncio.run(run(_session("faq", "assurance")))
    schema = json.loads(result.ld_json["ld_json"])
    assert "mainEntity" in schema


def test_fiche_produit_a_offers():
    result = asyncio.run(run(_session("fiche_produit", "enceinte")))
    schema = json.loads(result.ld_json["ld_json"])
    assert "offers" in schema


def test_service_local_a_address():
    result = asyncio.run(run(_session("service_local", "plombier")))
    schema = json.loads(result.ld_json["ld_json"])
    assert "address" in schema


# ─── 3. Entrée invalide ───────────────────────────────────────────────

def test_run_sans_seo():
    session = SessionState(keyword="test", type_page="article", config=SessionConfig(dry_run=True))
    result = asyncio.run(run(session))
    assert result.ld_json is not None


def test_run_type_inconnu():
    result = asyncio.run(run(_session("inexistant")))
    schema = json.loads(result.ld_json["ld_json"])
    assert schema["@type"] == "Article"


# ─── 4. Sortie conforme ────────────────────────────────────────────────

def test_schema_data_tous_les_champs():
    result = asyncio.run(run(_session()))
    for field in ("ld_json", "type_schema", "validation_errors"):
        assert field in result.ld_json


def test_ld_json_valide():
    result = asyncio.run(run(_session()))
    parsed = json.loads(result.ld_json["ld_json"])
    assert "@context" in parsed


def test_resultat_stocke():
    result = asyncio.run(run(_session()))
    assert result.agent_results["agent_21"].data == result.ld_json


def test_zero_cout():
    result = asyncio.run(run(_session()))
    assert result.agent_results["agent_21"].cost_estimated == 0.0


# ─── 5. Bibliotheque ──────────────────────────────────────────────────

def test_tous_les_types_couverts():
    for t in ("article", "pilier", "fiche_produit", "faq", "service_local",
              "comparatif", "landing", "news", "glossaire", "temoignage"):
        assert t in SCHEMA_TEMPLATES, f"Type {t} manquant dans SCHEMA_TEMPLATES"


def test_tous_callables():
    for fn in SCHEMA_TEMPLATES.values():
        assert callable(fn)
