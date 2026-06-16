"""Tests unitaires pour Agent 17 — Maillage externe."""

import asyncio
import pytest

from hermes.agents.agent_17_maillage_externe import (
    _extract_json, _mock_external, run,
)
from hermes.models.agent_data import ExternalLinks
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={"nom": "MonAssureur", "secteur": "finance"},
        serp_data={"concurrents_directs": ["assurland.com", "meilleurtaux.com"]},
        agent_results={
            "agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED),
        },
    )


def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.external_links is not None
    assert len(result.external_links["liens_sortants"]) >= 1
    assert result.agent_results["agent_17"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    ExternalLinks.model_validate(result.external_links)


def test_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    for field in ("liens_sortants", "sources_autorite", "pages_orphelines"):
        assert field in result.external_links


def test_liens_format_valide(session_valide):
    result = asyncio.run(run(session_valide))
    for lien in result.external_links["liens_sortants"]:
        assert "url_cible" in lien
        assert "autorite" in lien


def test_sources_autorite_finance(session_valide):
    result = asyncio.run(run(session_valide))
    sources = result.external_links["sources_autorite"]
    assert len(sources) >= 1


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_17"].data == result.external_links


def test_mock_external_secteur_finance():
    session = SessionState(keyword="test", config=SessionConfig(secteur="finance"))
    ext = _mock_external(session)
    assert any("service-public.fr" in s.url_cible for s in ext.liens_sortants)


def test_mock_external_secteur_sante():
    session = SessionState(keyword="test", config=SessionConfig(secteur="sante"))
    ext = _mock_external(session)
    assert any("ameli.fr" in s.url_cible for s in ext.liens_sortants)


def test_mock_external_sans_secteur():
    session = SessionState(keyword="test", config=SessionConfig())
    ext = _mock_external(session)
    assert len(ext.liens_sortants) >= 1


def test_extract_json_valide():
    assert _extract_json('{"sources_autorite": ["url"]}')["sources_autorite"] == ["url"]
