"""Tests unitaires pour Agent 08 — Anti-cannibalisation."""

import asyncio

import pytest

from hermes.agents.agent_08_anti_cannibalisation import (
    _heuristic_conflict, _extract_json, _build_llm_message, run,
)
from hermes.models.agent_data import AntiCannibData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        intention="informative",
        type_page="pilier",
        angles_differenciants={
            "angle_principal": "Guide exhaustif avec comparateur integre et donnees exclusives",
            "facteurs_differenciation": ["Comparateur integre", "Donnees proprietaires"],
        },
        agent_results={
            "agent_01": AgentResult(agent_id="agent_01", status=AgentStatus.COMPLETED),
            "agent_03": AgentResult(agent_id="agent_03", status=AgentStatus.COMPLETED),
            "agent_06": AgentResult(agent_id="agent_06", status=AgentStatus.COMPLETED),
        },
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.anti_cannib_data is not None
    assert "action" in result.anti_cannib_data
    assert result.anti_cannib_data["action"] in ("proceed", "merge", "enrich", "redirect", "abandon")
    assert result.agent_results["agent_08"].status == AgentStatus.COMPLETED


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_angles():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.anti_cannib_data["action"] == "proceed"


def test_run_sans_keyword():
    session = SessionState(keyword="", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.agent_results["agent_08"].status == AgentStatus.COMPLETED


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_anti_cannib_data_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    data = AntiCannibData.model_validate(result.anti_cannib_data)
    assert data.action in ("proceed", "merge", "enrich", "redirect", "abandon")


def test_pages_concurrentes_est_liste(session_valide):
    result = asyncio.run(run(session_valide))
    assert isinstance(result.anti_cannib_data["pages_concurrentes"], list)


def test_recommandation_non_vide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.anti_cannib_data["recommandation"]


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_08"].data == result.anti_cannib_data


# ─── 4. Heuristique de conflit ─────────────────────────────────────────

def test_heuristic_no_docs():
    conflit, pages, reco, action = _heuristic_conflict(
        SessionState(keyword="test"), {"documents": [], "metadatas": [], "distances": []}
    )
    assert not conflit
    assert action == "proceed"


def test_heuristic_low_similarity():
    """Documents avec faible similarite → pas de conflit."""
    similar = {
        "documents": [["doc1", "doc2"]],
        "metadatas": [[
            {"content_id": "a", "keyword": "autre", "intention": "informative"},
            {"content_id": "b", "keyword": "autre2", "intention": "transactionnelle"},
        ]],
        "distances": [[0.8, 0.85]],  # similarite = 0.2, 0.15
    }
    conflit, pages, reco, action = _heuristic_conflict(
        SessionState(keyword="test", intention="informative"), similar
    )
    assert not conflit
    assert action == "proceed"


def test_heuristic_high_similarity_same_intent():
    """Haute similarite + meme intention → conflit."""
    similar = {
        "documents": [["page existante sur le meme sujet"]],
        "metadatas": [[{"content_id": "old", "keyword": "assurance vie", "intention": "informative"}]],
        "distances": [[0.2]],  # similarite = 0.8
    }
    conflit, pages, reco, action = _heuristic_conflict(
        SessionState(keyword="assurance vie", intention="informative"), similar
    )
    assert conflit
    assert action == "enrich"


def test_heuristic_high_similarity_different_intent():
    """Haute similarite mais intention differente → OK."""
    similar = {
        "documents": [["page existante"]],
        "metadatas": [[{"content_id": "old", "keyword": "assurance vie", "intention": "informative"}]],
        "distances": [[0.2]],  # similarite = 0.8
    }
    conflit, pages, reco, action = _heuristic_conflict(
        SessionState(keyword="assurance vie", intention="transactionnelle"), similar
    )
    assert not conflit
    assert action == "proceed"


# ─── 5. Build LLM message ──────────────────────────────────────────────

def test_build_llm_message_contient_pages():
    pages = [{"content_id": "a", "keyword": "test", "intention": "info", "similarity": 0.8}]
    session = SessionState(keyword="test", intention="informative")
    msg = _build_llm_message(session, pages)
    assert "test" in msg


# ─── 6. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"action": "merge"}')["action"] == "merge"


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
