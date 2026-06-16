"""Tests unitaires pour Agent 11 — AEO (Answer Engine Optimization)."""

import asyncio

import pytest

from hermes.agents.agent_11_aeo import (
    _extract_json, _build_user_message, _mock_aeo, run,
)
from hermes.models.agent_data import AeoBlocks
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_article():
    return SessionState(
        keyword="assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        intention="informative",
        type_page="article",
        brouillon_html="<h1>Guide</h1><p>Contenu informatif sur l'assurance vie.</p>",
        serp_data={
            "paa": ["Qu'est-ce que l'assurance vie ?", "Comment ca marche ?",
                     "Quel prix ?", "Comment choisir ?"],
            "ai_overviews": [{"content": "L'assurance vie temporaire protege..."}],
        },
        offre_conversion_data={"cta_principal": "Demandez un devis"},
        agent_results={"agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED)},
    )


# ─── 1. Entree valide ─────────────────────────────────────────────────

def test_run_article(session_article):
    result = asyncio.run(run(session_article))
    assert result.aeo_blocks["en_bref"]
    assert len(result.aeo_blocks["h2_questions"]) >= 3
    assert result.agent_results["agent_11"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_article):
    result = asyncio.run(run(session_article))
    AeoBlocks.model_validate(result.aeo_blocks)


# ─── 2. Entree invalide ────────────────────────────────────────────────

def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.aeo_blocks["en_bref"]


def test_run_sans_serp():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
                           brouillon_html="<h1>Test</h1><p>Contenu</p>")
    result = asyncio.run(run(session))
    assert result.agent_results["agent_11"].status == AgentStatus.COMPLETED


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_tous_les_champs(session_article):
    result = asyncio.run(run(session_article))
    for field in ("en_bref", "h2_questions", "faq", "definitions"):
        assert field in result.aeo_blocks, f"Champ manquant: {field}"


def test_h2_questions_sont_des_questions(session_article):
    result = asyncio.run(run(session_article))
    assert any("?" in q for q in result.aeo_blocks["h2_questions"])


def test_faq_format_valide(session_article):
    for entry in asyncio.run(run(session_article)).aeo_blocks["faq"]:
        assert "question" in entry and "reponse" in entry


def test_definitions_format_valide(session_article):
    for entry in asyncio.run(run(session_article)).aeo_blocks["definitions"]:
        assert "terme" in entry and "definition" in entry


def test_resultat_stocke(session_article):
    result = asyncio.run(run(session_article))
    assert result.agent_results["agent_11"].data == result.aeo_blocks


# ─── 4. Mock dry-run par type de page ──────────────────────────────────

def test_mock_article_utilise_paa(session_article):
    aeo = _mock_aeo(session_article)
    assert len(aeo.h2_questions) >= 3
    assert len(aeo.faq) >= 2
    assert len(aeo.definitions) >= 1


def test_mock_fiche_produit():
    session = SessionState(keyword="enceinte bluetooth", type_page="fiche_produit")
    aeo = _mock_aeo(session)
    assert "produit" in aeo.en_bref.lower()
    assert len(aeo.h2_questions) >= 1
    assert any("prix" in q.lower() for q in aeo.h2_questions)
    assert len(aeo.faq) >= 1
    assert len(aeo.definitions) >= 1  # SKU


def test_mock_landing():
    session = SessionState(
        keyword="logiciel crm", type_page="landing",
        offre_conversion_data={"valeur_ajoutee_unique": "Le CRM le plus simple du marche"},
    )
    aeo = _mock_aeo(session)
    assert "CRM" in aeo.en_bref
    assert any("pourquoi" in q.lower() for q in aeo.h2_questions)
    assert len(aeo.faq) >= 1
    assert aeo.definitions == []  # Pas pertinent pour une landing


def test_mock_comparatif():
    session = SessionState(keyword="meilleur aspirateur", type_page="comparatif")
    aeo = _mock_aeo(session)
    assert "comparatif" in aeo.en_bref.lower()
    assert any("meilleur" in q.lower() for q in aeo.h2_questions)
    assert aeo.definitions == []  # Pas pertinent pour un comparatif


def test_mock_service_local():
    session = SessionState(keyword="plombier Paris 15", type_page="service_local")
    aeo = _mock_aeo(session)
    assert "proximite" in aeo.en_bref.lower()
    assert any("pres de chez moi" in q.lower() for q in aeo.h2_questions)
    assert aeo.definitions == []  # Pas pertinent pour un service local


def test_mock_pilier():
    session = SessionState(keyword="guide complet", type_page="pilier")
    aeo = _mock_aeo(session)
    assert len(aeo.faq) >= 2
    assert len(aeo.definitions) >= 1


def test_mock_news():
    session = SessionState(keyword="nouvelle loi", type_page="news")
    aeo = _mock_aeo(session)
    assert len(aeo.h2_questions) >= 3


# ─── 5. Build user message adapte au type ──────────────────────────────

def test_build_message_article(session_article):
    msg = _build_user_message(session_article)
    assert "en_bref" in msg
    assert "h2_questions" in msg


def test_build_message_produit():
    session = SessionState(keyword="test", type_page="fiche_produit",
                           config=SessionConfig(dry_run=True))
    msg = _build_user_message(session)
    assert "Fiche technique" in msg


def test_build_message_landing():
    session = SessionState(keyword="test", type_page="landing",
                           config=SessionConfig(dry_run=True))
    msg = _build_user_message(session)
    assert "Proposition de valeur" in msg


def test_build_message_comparatif():
    session = SessionState(keyword="test", type_page="comparatif",
                           config=SessionConfig(dry_run=True))
    msg = _build_user_message(session)
    assert "methodologie" in msg


# ─── 6. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"en_bref": "test"}')["en_bref"] == "test"


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
