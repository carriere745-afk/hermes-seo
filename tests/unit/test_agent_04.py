"""Tests unitaires pour Agent 04 — Intention & Type de page."""

import asyncio

import pytest

from hermes.agents.agent_04_intention import (
    _classify_intent_heuristic,
    _classify_type_heuristic,
    _extract_json,
    _build_user_message,
    _mock_intent,
    run,
)
from hermes.models.agent_data import IntentTypeData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="comment fonctionne l'assurance vie temporaire",
        site_url="https://www.monassureur.fr",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={"nom": "MonAssureur", "secteur": "finance", "positionnement": "Courtier"},
        fiche_persona={"nom_persona": "Paul", "maturite": "intermediaire"},
        serp_data={
            "top10": [
                {"position": 1, "title": "Guide complet assurance vie temporaire", "url": "https://exemple.fr/guide", "snippet": "Tout savoir...", "domain": "exemple.fr"},
                {"position": 2, "title": "Definition et fonctionnement", "url": "https://exemple2.fr", "snippet": "...", "domain": "exemple2.fr"},
                {"position": 3, "title": "Comment choisir son assurance vie ?", "url": "https://exemple3.fr", "snippet": "...", "domain": "exemple3.fr"},
            ],
            "paa": [
                "Qu'est-ce que l'assurance vie temporaire ?",
                "Comment ca fonctionne ?",
                "Quel est le prix ?",
                "Comment choisir ?",
                "Quelles sont les garanties ?",
                "Quelle duree choisir ?",
            ],
            "concurrents_directs": ["assurland.com", "meilleurtaux.com"],
        },
        agent_results={
            "agent_01": AgentResult(agent_id="agent_01", status=AgentStatus.COMPLETED),
            "agent_02": AgentResult(agent_id="agent_02", status=AgentStatus.COMPLETED),
            "agent_03": AgentResult(agent_id="agent_03", status=AgentStatus.COMPLETED),
        },
    )


@pytest.fixture
def session_transactionnelle():
    return SessionState(
        keyword="acheter assurance vie en ligne",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        serp_data={
            "top10": [
                {"position": 1, "title": "Souscrire assurance vie - Prix 2026", "url": "https://exemple.fr", "snippet": "A partir de 10eur/mois...", "domain": "exemple.fr"},
                {"position": 2, "title": "Acheter assurance vie pas cher", "url": "https://exemple2.fr", "snippet": "Devis gratuit...", "domain": "exemple2.fr"},
            ],
            "paa": [],
        },
        agent_results={
            "agent_01": AgentResult(agent_id="agent_01", status=AgentStatus.COMPLETED),
            "agent_03": AgentResult(agent_id="agent_03", status=AgentStatus.COMPLETED),
        },
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.intention is not None
    assert result.type_page is not None
    assert result.agent_results["agent_04"].status == AgentStatus.COMPLETED


def test_run_classifie_correctement(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.intention == "informative"


def test_run_transactionnelle(session_transactionnelle):
    result = asyncio.run(run(session_transactionnelle))
    assert result.intention in ("transactionnelle", "informative")


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    data = result.agent_results["agent_04"].data
    intent_data = IntentTypeData.model_validate(data)
    assert intent_data.intention
    assert intent_data.type_page


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_serp():
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    result = asyncio.run(run(session))
    assert result.intention is not None
    assert result.type_page is not None


def test_run_keyword_vide():
    session = SessionState(
        keyword="",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    result = asyncio.run(run(session))
    assert result.intention == "informative"


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_intention_parmi_valeurs_valides(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.intention in ("informative", "transactionnelle", "comparative", "locale", "navigationnelle")


def test_type_page_parmi_valeurs_valides(session_valide):
    result = asyncio.run(run(session_valide))
    valid_types = ("article", "pilier", "fiche_produit", "faq", "service_local",
                   "comparatif", "landing", "news", "glossaire", "temoignage")
    assert result.type_page in valid_types


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_04"].data["intention"] == result.intention
    assert result.agent_results["agent_04"].data["type_page"] == result.type_page


# ─── 4. Heuristiques ───────────────────────────────────────────────────

def test_classify_intent_informative():
    assert _classify_intent_heuristic("comment fonctionne l'assurance vie") == "informative"


def test_classify_intent_transactionnelle():
    assert _classify_intent_heuristic("acheter assurance vie pas cher") == "transactionnelle"


def test_classify_intent_comparative():
    assert _classify_intent_heuristic("meilleur assurance vie comparatif") == "comparative"


def test_classify_intent_defaut():
    assert _classify_intent_heuristic("assurance vie") == "informative"


def test_classify_type_pilier_paa():
    serp = {"paa": ["q1", "q2", "q3", "q4", "q5", "q6"], "top10": []}
    assert _classify_type_heuristic("guide complet assurance vie", "informative", serp) == "pilier"


def test_classify_type_produit():
    serp = {
        "top10": [
            {"title": "Acheter assurance vie - Prix 2026"},
            {"title": "Assurance vie pas cher - Boutique"},
            {"title": "Devis assurance vie en ligne"},
        ]
    }
    result = _classify_type_heuristic("acheter assurance vie", "transactionnelle", serp)
    assert result in ("fiche_produit", "landing")


def test_classify_type_explicite():
    assert _classify_type_heuristic("faq assurance vie", "informative") == "faq"


# ─── 5. Mock dry-run ───────────────────────────────────────────────────

def test_mock_intent_informative():
    data = _mock_intent("comment investir en bourse", None, "finance")
    assert data.intention == "informative"
    assert data.type_page in ("article", "pilier")


def test_mock_intent_transactionnelle():
    data = _mock_intent("acheter action total", None, None)
    assert data.intention == "transactionnelle"


def test_mock_intent_locale():
    data = _mock_intent("assureur pres de chez moi paris", None, None)
    assert data.intention == "locale"


def test_mock_intent_comparative():
    data = _mock_intent("meilleur assurance vie vs placement", None, None)
    assert data.intention == "comparative"


# ─── 6. Build user message ─────────────────────────────────────────────

def test_build_message_contient_keyword(session_valide):
    msg = _build_user_message(session_valide)
    assert "assurance vie temporaire" in msg


def test_build_message_sans_serp():
    session = SessionState(keyword="test")
    msg = _build_user_message(session)
    assert "Non disponible" in msg


# ─── 7. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"intention": "informative"}')["intention"] == "informative"


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
