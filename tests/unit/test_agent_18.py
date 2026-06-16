"""Tests unitaires pour Agent 18 — Multiformat."""

import asyncio
import pytest

from hermes.agents.agent_18_multiformat import (
    _extract_json, _mock_multiformat, run, _build_user_message,
)
from hermes.models.agent_data import MultiformatData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="guide complet assurance vie",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        fiche_entreprise={"nom": "MonAssureur"},
        offre_conversion_data={"cta_principal": "Demandez votre devis"},
        brouillon_html=("<h1>Guide Assurance Vie</h1><p>Contenu complet sur l'assurance vie "
                         "temporaire. Definition, fonctionnement, avantages et conseils.</p>"),
        agent_results={
            "agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED),
        },
    )


def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.multiformat_data is not None
    assert result.multiformat_data["thread_linkedin"]
    assert result.multiformat_data["script_youtube"]
    assert result.multiformat_data["newsletter"]
    assert len(result.multiformat_data["social_posts"]) >= 2
    assert result.agent_results["agent_18"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    MultiformatData.model_validate(result.multiformat_data)


def test_session_parent_present(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.multiformat_data["session_parent"] == session_valide.session_id


def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.multiformat_data is not None


def test_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    for field in ("thread_linkedin", "script_youtube", "newsletter", "social_posts", "session_parent"):
        assert field in result.multiformat_data


def test_thread_contient_hook(session_valide):
    result = asyncio.run(run(session_valide))
    assert "1/" in result.multiformat_data["thread_linkedin"]


def test_social_posts_trois(session_valide):
    result = asyncio.run(run(session_valide))
    assert len(result.multiformat_data["social_posts"]) <= 5


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_18"].data == result.multiformat_data


def test_mock_multiformat_thread():
    session = SessionState(keyword="test", fiche_entreprise={"nom": "Corp"})
    multi = _mock_multiformat(session)
    assert "1/" in multi.thread_linkedin
    assert "INTRO" in multi.script_youtube
    assert "Objet" in multi.newsletter
    assert len(multi.social_posts) == 3


def test_build_user_message():
    session = SessionState(keyword="test", fiche_entreprise={"nom": "Corp"},
                           offre_conversion_data={"cta_principal": "Essayez"})
    msg = _build_user_message(session, "contenu test")
    assert "test" in msg and "Corp" in msg


def test_extract_json_valide():
    assert _extract_json('{"newsletter": "test"}')["newsletter"] == "test"


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
