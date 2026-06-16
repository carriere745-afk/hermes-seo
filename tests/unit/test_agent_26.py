"""Tests unitaires pour Agent 26 — Audit post-publication."""

import asyncio, pytest

from hermes.agents.agent_26_audit_post_publication import (
    _mock_gsc_data, _correlate, _learnings, _extract_json, run,
)
from hermes.models.agent_data import FeedbackData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_publiee():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        session_id="test-session-abc123",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        site_url="https://www.monassureur.fr/guide-assurance-vie",
        brouillon_html="<h1>Guide Assurance Vie</h1><p>Contenu publie de qualite.</p>",
        scores={"score_total": 82, "scores": {"lisibilite": 8, "densite_semantique": 12}},
        intention="informative",
        angles_differenciants={"angle_principal": "Guide exhaustif avec comparateur integre"},
        agent_results={
            "agent_25": AgentResult(agent_id="agent_25", status=AgentStatus.COMPLETED),
        },
    )


# ─── 1. Entree valide ────────────────────────────────────────────────

def test_run_produit_feedback(session_publiee):
    result = asyncio.run(run(session_publiee))
    assert result.feedback_data is not None
    assert "clicks" in result.feedback_data["data_gsc"]
    assert result.feedback_data["data_gsc"]["position"] > 0
    assert len(result.feedback_data["apprentissages"]) >= 2
    assert result.agent_results["agent_26"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_publiee):
    FeedbackData.model_validate(asyncio.run(run(session_publiee)).feedback_data)


# ─── 2. Entree invalide ───────────────────────────────────────────────

def test_run_sans_scores():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.feedback_data is not None


def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.agent_results["agent_26"].status == AgentStatus.COMPLETED


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_feedback_tous_les_champs(session_publiee):
    result = asyncio.run(run(session_publiee))
    for field in ("data_gsc", "correlation", "apprentissages", "ajustements_memoire"):
        assert field in result.feedback_data, f"Champ manquant: {field}"


def test_correlation_contient_match(session_publiee):
    result = asyncio.run(run(session_publiee))
    assert "match_qualite" in result.feedback_data["correlation"]


def test_apprentissages_non_vides(session_publiee):
    result = asyncio.run(run(session_publiee))
    assert len(result.feedback_data["apprentissages"]) >= 2


def test_resultat_stocke(session_publiee):
    result = asyncio.run(run(session_publiee))
    assert result.agent_results["agent_26"].data == result.feedback_data


def test_last_completed_agent_id(session_publiee):
    result = asyncio.run(run(session_publiee))
    assert result.last_completed_agent_id == "agent_26"


# ─── 4. Mock GSC ──────────────────────────────────────────────────────

def test_mock_gsc_a_toutes_les_cles():
    gsc = _mock_gsc_data(SessionState(keyword="test"))
    for key in ("query", "clicks", "impressions", "ctr", "position",
                "top_queries", "top_pages"):
        assert key in gsc, f"Cle manquante: {key}"


def test_mock_gsc_perf_correlee_score():
    """Un meilleur score produit de meilleures perfs simulees."""
    session_bon = SessionState(keyword="test", scores={"score_total": 90})
    session_moyen = SessionState(keyword="test", scores={"score_total": 50})
    assert _mock_gsc_data(session_bon)["clicks"] > _mock_gsc_data(session_moyen)["clicks"]


# ─── 5. Correlation ───────────────────────────────────────────────────

def test_correlation_bon_score_bonne_perf():
    gsc = {"position": 5, "ctr": 0.06, "clicks": 200}
    session = SessionState(keyword="test", scores={"score_total": 82})
    corr = _correlate(session, gsc)
    assert "Bonne correlation" in corr["match_qualite"]


def test_correlation_bon_score_mauvaise_perf():
    gsc = {"position": 15, "ctr": 0.02, "clicks": 30}
    session = SessionState(keyword="test", scores={"score_total": 85})
    corr = _correlate(session, gsc)
    assert "Decalage" in corr["match_qualite"]


# ─── 6. Learnings ─────────────────────────────────────────────────────

def test_learnings_top3():
    gsc = {"position": 2, "ctr": 0.08, "top_queries": [{"query": "a"}, {"query": "b"}, {"query": "c"}]}
    session = SessionState(keyword="test", scores={"score_total": 90})
    corr = _correlate(session, gsc)
    apps = _learnings(session, gsc, corr)
    assert any("top 3" in a.lower() for a in apps)


def test_learnings_page2():
    gsc = {"position": 15, "ctr": 0.015, "top_queries": [{"query": "a"}]}
    session = SessionState(keyword="test", scores={"score_total": 65})
    corr = _correlate(session, gsc)
    apps = _learnings(session, gsc, corr)
    assert any("page 2" in a.lower() for a in apps)


# ─── 7. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"apprentissages_llm": ["a"]}')["apprentissages_llm"] == ["a"]


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
