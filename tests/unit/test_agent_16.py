"""Tests unitaires pour Agent 16 — Maillage interne."""

import asyncio
import pytest

from hermes.agents.agent_16_maillage_interne import (
    _extract_json, _mock_liens, run,
)
from hermes.models.agent_data import InternalLinks
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        type_page="pilier",
        brouillon_html="<h1>Guide</h1><p>Contenu complet sur l'assurance vie.</p>",
        agent_results={
            "agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED),
        },
    )


def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.internal_links is not None
    assert len(result.internal_links["liens_proposes"]) >= 2
    assert result.agent_results["agent_16"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    InternalLinks.model_validate(result.internal_links)


def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.internal_links is not None


def test_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    for field in ("liens_proposes", "ancres_suggerees", "pages_pilier"):
        assert field in result.internal_links


def test_liens_format_valide(session_valide):
    result = asyncio.run(run(session_valide))
    for lien in result.internal_links["liens_proposes"]:
        assert "url_cible" in lien
        assert "ancre_suggeree" in lien


def test_pages_pilier_non_vide(session_valide):
    result = asyncio.run(run(session_valide))
    assert len(result.internal_links["pages_pilier"]) >= 1


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_16"].data == result.internal_links


def test_mock_liens_avec_memoire():
    similar = {"documents": [["doc1"]], "metadatas": [[{"url": "/article-1", "keyword": "test"}]]}
    liens = _mock_liens(SessionState(keyword="test"), similar)
    assert len(liens.liens_proposes) >= 1


def test_mock_liens_sans_memoire():
    liens = _mock_liens(SessionState(keyword="test"), {})
    assert len(liens.liens_proposes) >= 2


def test_extract_json_valide():
    assert _extract_json('{"pages_pilier": ["/p1"]}')["pages_pilier"] == ["/p1"]


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
