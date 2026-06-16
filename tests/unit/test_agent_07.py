"""Tests unitaires pour Agent 07 — Template."""

import asyncio

import pytest

from hermes.agents.agent_07_template import (
    _select_template, _extract_json, _build_llm_message, TEMPLATES, run,
)
from hermes.models.agent_data import TemplateData, Section
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_pilier():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        intention="informative",
        type_page="pilier",
        offre_conversion_data={"cta_principal": "Telechargez le guide complet"},
        serp_data={
            "top10": [
                {"position": 1, "title": "Guide assurance vie", "domain": "test.fr", "snippet": "...", "url": "https://..."},
            ],
        },
        agent_results={
            "agent_04": AgentResult(agent_id="agent_04", status=AgentStatus.COMPLETED),
        },
    )


@pytest.fixture
def session_article():
    return SessionState(
        keyword="comment fonctionne le credit immobilier",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        intention="informative",
        type_page="article",
        agent_results={
            "agent_04": AgentResult(agent_id="agent_04", status=AgentStatus.COMPLETED),
        },
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_pilier(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert result.template_data is not None
    assert result.template_data["template_id"] == "pilier"
    assert len(result.template_data["structure"]) >= 5
    assert result.agent_results["agent_07"].status == AgentStatus.COMPLETED


def test_run_avec_session_article(session_article):
    result = asyncio.run(run(session_article))
    assert result.template_data["template_id"] == "article"


def test_run_pydantic_valide(session_pilier):
    result = asyncio.run(run(session_pilier))
    tmpl = TemplateData.model_validate(result.template_data)
    assert tmpl.template_id
    assert len(tmpl.structure) > 0
    assert all(isinstance(s, Section) or hasattr(s, 'type') for s in tmpl.structure)


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_type_page():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.template_data["template_id"] == "article"  # defaut


def test_run_type_inconnu():
    session = SessionState(keyword="test", type_page="inexistant", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.template_data["template_id"] == "article"


def test_run_keyword_vide():
    session = SessionState(keyword="", type_page="faq", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.template_data["template_id"] == "faq"


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_template_structure_valide(session_pilier):
    result = asyncio.run(run(session_pilier))
    structure = result.template_data["structure"]
    assert len(structure) >= 3
    types = {s["type"] for s in structure}
    assert "h1" in types
    assert "intro" in types or any(s["type"] == "intro" for s in structure)


def test_sections_ordonnees(session_pilier):
    result = asyncio.run(run(session_pilier))
    ordres = [s["ordre"] for s in result.template_data["structure"]]
    assert ordres == sorted(ordres)


def test_h1_est_premiere_section(session_pilier):
    result = asyncio.run(run(session_pilier))
    first = result.template_data["structure"][0]
    assert first["type"] == "h1"


def test_resultat_stocke(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert result.agent_results["agent_07"].data == result.template_data
    assert result.last_completed_agent_id == "agent_07"


# ─── 4. Tous les types de page ─────────────────────────────────────────

@pytest.mark.parametrize("type_page", [
    "article", "pilier", "fiche_produit", "faq", "service_local",
    "comparatif", "landing", "news", "glossaire", "temoignage",
])
def test_template_existe_pour_chaque_type(type_page):
    session = SessionState(
        keyword="test", type_page=type_page,
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    result = asyncio.run(run(session))
    assert result.template_data["template_id"] == type_page
    assert len(result.template_data["structure"]) >= 3


def test_pilier_a_faq_et_en_bref(session_pilier):
    result = asyncio.run(run(session_pilier))
    titres = {s["titre"] for s in result.template_data["structure"]}
    assert any("FAQ" in t for t in titres), f"Pas de section FAQ dans: {titres}"
    assert any("bref" in t.lower() for t in titres), f"Pas de section En bref dans: {titres}"


def test_landing_a_cta():
    session = SessionState(keyword="test", type_page="landing",
                           config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    types = {s["type"] for s in result.template_data["structure"]}
    assert "cta" in types


def test_comparatif_a_au_moins_6_sections():
    session = SessionState(keyword="test", type_page="comparatif",
                           config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.template_data["nb_sections"] >= 6


# ─── 5. Bibliotheque de templates ──────────────────────────────────────

def test_select_template_pilier():
    tmpl = _select_template("pilier", "informative", "assurance vie")
    assert tmpl.template_id == "pilier"
    assert tmpl.nb_sections == 11


def test_select_template_enrichit_avec_keyword():
    tmpl = _select_template("pilier", "informative", "assurance vie")
    h1 = tmpl.structure[0]
    assert "assurance vie" in h1.titre.lower()


def test_select_template_transactionnel_pilier_devient_landing():
    tmpl = _select_template("pilier", "transactionnelle", "acheter")
    assert tmpl.template_id == "landing"


def test_select_template_inconnu_retourne_article():
    tmpl = _select_template("inexistant", "informative", "test")
    assert tmpl.template_id == "article"


# ─── 6. Build LLM message ──────────────────────────────────────────────

def test_build_llm_message_contient_keyword(session_pilier):
    msg = _build_llm_message(session_pilier)
    assert "assurance vie" in msg


# ─── 7. Bibliotheque complete ──────────────────────────────────────────

def test_tous_les_templates_dans_bibliotheque():
    types = ["article", "pilier", "fiche_produit", "faq", "service_local",
             "comparatif", "landing", "news", "glossaire", "temoignage"]
    for t in types:
        assert t in TEMPLATES, f"Type {t} manquant dans TEMPLATES"


def test_tous_les_templates_ont_h1():
    for tid, sections in TEMPLATES.items():
        types = {s["type"] for s in sections}
        assert "h1" in types, f"Template {tid} manque de h1"


def test_tous_les_templates_ont_sections_obligatoires():
    for tid, sections in TEMPLATES.items():
        obligatoires = [s for s in sections if s.get("obligatoire", True)]
        assert len(obligatoires) >= 2, f"Template {tid} a moins de 2 sections obligatoires"
