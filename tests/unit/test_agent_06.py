"""Tests unitaires pour Agent 06 — Differenciation concurrentielle."""

import asyncio

import pytest

from hermes.agents.agent_06_differenciation import (
    _extract_json, _build_user_message, _mock_differenciation, run,
)
from hermes.models.agent_data import DifferenciationData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={
            "nom": "MonAssureur", "secteur": "finance",
            "positionnement": "Courtier 100% digital",
            "elements_differenciants": ["Souscription en ligne", "Comparateur integre", "Application mobile"],
        },
        offre_conversion_data={
            "valeur_ajoutee_unique": "La seule assurance vie 100% digitale avec comparateur integre",
            "preuves": ["Agree AMF", "100 000 clients"],
            "benefices": ["Gagnez du temps", "Economisez jusqu'a 30%"],
        },
        serp_data={
            "top10": [
                {"position": 1, "title": "Assurance vie : definition et fonctionnement", "domain": "assurland.com", "snippet": "...", "url": "https://..."},
                {"position": 2, "title": "Comment choisir son assurance vie", "domain": "meilleurtaux.com", "snippet": "...", "url": "https://..."},
                {"position": 3, "title": "Guide assurance vie 2024", "domain": "lesfurets.com", "snippet": "...", "url": "https://..."},
            ],
            "concurrents_directs": ["assurland.com", "meilleurtaux.com", "lesfurets.com"],
        },
        agent_results={
            "agent_01": AgentResult(agent_id="agent_01", status=AgentStatus.COMPLETED),
            "agent_03": AgentResult(agent_id="agent_03", status=AgentStatus.COMPLETED),
            "agent_05": AgentResult(agent_id="agent_05", status=AgentStatus.COMPLETED),
        },
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.angles_differenciants is not None
    assert len(result.angles_differenciants["angles_faibles"]) >= 1
    assert result.angles_differenciants["angle_principal"]
    assert result.agent_results["agent_06"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    diff = DifferenciationData.model_validate(result.angles_differenciants)
    assert diff.angle_principal


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_serp():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.angles_differenciants is not None
    assert result.agent_results["agent_06"].status == AgentStatus.COMPLETED


def test_run_keyword_vide():
    session = SessionState(keyword="", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.angles_differenciants["facteurs_differenciation"]


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    data = result.angles_differenciants
    for field in ("angles_faibles", "opportunites_uniques", "angle_principal", "facteurs_differenciation"):
        assert field in data, f"Champ manquant: {field}"
    assert isinstance(data["angles_faibles"], list)
    assert isinstance(data["opportunites_uniques"], list)


def test_angle_principal_non_vide(session_valide):
    result = asyncio.run(run(session_valide))
    assert len(result.angles_differenciants["angle_principal"]) > 10


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_06"].data == result.angles_differenciants


# ─── 4. Mock dry-run ───────────────────────────────────────────────────

def test_mock_utilise_elements_differenciants(session_valide):
    diff = _mock_differenciation(session_valide)
    assert any("Souscription" in f or "Comparateur" in f or "Application" in f
               for f in diff.facteurs_differenciation)


def test_mock_fallbacks_sans_donnees():
    session = SessionState(keyword="test", config=SessionConfig(dry_run=True))
    diff = _mock_differenciation(session)
    assert diff.angles_faibles
    assert diff.opportunites_uniques
    assert diff.angle_principal


# ─── 5. Build user message ─────────────────────────────────────────────

def test_build_message_contient_concurrents(session_valide):
    msg = _build_user_message(session_valide)
    assert "assurland.com" in msg


def test_build_message_sans_serp():
    session = SessionState(keyword="test")
    msg = _build_user_message(session)
    assert "Non disponible" in msg or "Non identifies" in msg


# ─── 6. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    data = _extract_json('{"angle_principal": "test", "angles_faibles": ["a"]}')
    assert data["angle_principal"] == "test"


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
