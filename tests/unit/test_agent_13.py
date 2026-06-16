"""Tests unitaires pour Agent 13 — EEAT."""

import asyncio

import pytest

from hermes.agents.agent_13_eeat import (
    _heuristic_eeat, _extract_json, _strip_html, _build_user_message, run,
)
from hermes.models.agent_data import EeatScore
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={
            "nom": "MonAssureur", "secteur": "finance",
            "positionnement": "Courtier 100% digital agree AMF",
            "preuves": ["Agree AMF", "100 000 clients", "Application mobile 4.8/5"],
            "elements_differenciants": ["Souscription en ligne", "Comparateur integre"],
        },
        brouillon_html=(
            "<h1>Guide Complet Assurance Vie Temporaire</h1>"
            "<p><strong>L'assurance vie temporaire</strong> est un contrat qui protege "
            "vos proches en cas de deces. Selon la Federation Francaise de l'Assurance, "
            "plus de 10 millions de Francais sont couverts par ce type de contrat.</p>"
            "<p>Dans notre experience de courtier agree AMF, nous avons constate que "
            "80% de nos clients sous-estiment le capital necessaire. Voici un exemple "
            "concret : Paul, 45 ans, a souscrit un capital de 200 000 euros pour une "
            "prime mensuelle de 25 euros.</p>"
            "<p>Source : Federation Francaise de l'Assurance, Rapport annuel 2025.</p>"
            "<p>Mentions legales : Ce produit presente un risque de perte en capital. "
            "Document a jour au 1er janvier 2026.</p>"
            "<p>Contact : service-client@monassureur.fr — 01 23 45 67 89</p>"
        ),
        agent_results={
            "agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED),
        },
    )


@pytest.fixture
def session_faible():
    return SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="saas"),
        fiche_entreprise={"nom": "Startup", "secteur": "saas"},
        brouillon_html="<h1>Test</h1><p>Contenu vague sans source ni exemple.</p>",
    )


# ─── 1. Entree valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.score_eeat is not None
    for field in ("score_expertise", "score_experience", "score_autorite", "score_fiabilite"):
        assert 0 <= result.score_eeat[field] <= 4
    assert 0 <= result.score_eeat["score_global"] <= 16
    assert result.agent_results["agent_13"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    EeatScore.model_validate(result.score_eeat)


# ─── 2. Entree invalide ────────────────────────────────────────────────

def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.score_eeat is not None


def test_run_sans_entreprise():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
                           brouillon_html="<h1>Test</h1><p>Contenu</p>")
    result = asyncio.run(run(session))
    assert result.agent_results["agent_13"].status == AgentStatus.COMPLETED


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_eeat_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    for field in ("score_expertise", "score_experience", "score_autorite",
                  "score_fiabilite", "score_global", "recommandations"):
        assert field in result.score_eeat, f"Champ manquant: {field}"


def test_scores_dans_limites(session_valide):
    result = asyncio.run(run(session_valide))
    for field in ("score_expertise", "score_experience", "score_autorite", "score_fiabilite"):
        assert 0 <= result.score_eeat[field] <= 4, f"{field} hors limites"


def test_recommandations_sont_liste(session_valide):
    result = asyncio.run(run(session_valide))
    assert isinstance(result.score_eeat["recommandations"], list)


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_13"].data == result.score_eeat


# ─── 4. Heuristique EEAT ──────────────────────────────────────────────

def test_heuristic_content_riche_score_eleve(session_valide):
    text = _strip_html(session_valide.brouillon_html or "")
    eeat = _heuristic_eeat(text, session_valide.fiche_entreprise or {}, "finance")
    assert eeat.score_global >= 4  # Contenu riche en signaux


def test_heuristic_content_faible_score_bas(session_faible):
    text = _strip_html(session_faible.brouillon_html or "")
    eeat = _heuristic_eeat(text, session_faible.fiche_entreprise or {}, "saas")
    assert eeat.score_expertise <= 2


def test_heuristic_sans_entreprise():
    eeat = _heuristic_eeat("contenu basique", {}, None)
    assert 0 <= eeat.score_global <= 16


def test_heuristic_recommandations_non_vides_quand_score_bas(session_faible):
    text = _strip_html(session_faible.brouillon_html or "")
    eeat = _heuristic_eeat(text, session_faible.fiche_entreprise or {}, "saas")
    if eeat.score_global < 12:
        assert len(eeat.recommandations) > 0


# ─── 5. Strip HTML ─────────────────────────────────────────────────────

def test_strip_html():
    text = _strip_html("<h1>Titre</h1><p>Paragraphe.</p>")
    assert "Titre" in text
    assert "Paragraphe" in text


# ─── 6. Build user message ─────────────────────────────────────────────

def test_build_message(session_valide):
    text = _strip_html(session_valide.brouillon_html or "")
    msg = _build_user_message(session_valide, text)
    assert "MonAssureur" in msg
    assert "score_expertise" in msg


# ─── 7. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"score_global": 12}')["score_global"] == 12


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
