"""Tests unitaires pour Agent 20 — Localisation."""

import asyncio
import pytest

from hermes.agents.agent_20_localisation import (
    _build_hreflang, _mock_localisation, _extract_json, LOCALE_ADAPTATIONS, run,
)
from hermes.models.agent_data import LocalisedData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_avec_locales():
    return SessionState(
        keyword="guide complet assurance vie",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True,
                            target_locales=["fr-be", "fr-ch", "en"], secteur="finance"),
        brouillon_html="<h1>Guide Assurance Vie</h1><p>Contenu sur l'assurance vie en France.</p>",
        site_url="https://www.monassureur.fr/guide",
    )


@pytest.fixture
def session_sans_locales():
    return SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, target_locales=[]),
    )


# ─── 1. Entree valide ────────────────────────────────────────────────

def test_run_avec_locales(session_avec_locales):
    result = asyncio.run(run(session_avec_locales))
    assert result.localised_data is not None
    assert len(result.localised_data["versions"]) == 3
    assert result.localised_data["hreflang_tags"]
    assert len(result.localised_data["adaptations"]) == 3
    assert result.agent_results["agent_20"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_avec_locales):
    result = asyncio.run(run(session_avec_locales))
    LocalisedData.model_validate(result.localised_data)


# ─── 2. Entree invalide ───────────────────────────────────────────────

def test_run_sans_locales(session_sans_locales):
    result = asyncio.run(run(session_sans_locales))
    assert result.localised_data is not None
    assert result.localised_data["versions"] == {}


# ─── 3. Sortie conforme ───────────────────────────────────────────────

def test_localised_tous_les_champs(session_avec_locales):
    result = asyncio.run(run(session_avec_locales))
    for field in ("versions", "hreflang_tags", "adaptations"):
        assert field in result.localised_data


def test_versions_sont_des_locales(session_avec_locales):
    result = asyncio.run(run(session_avec_locales))
    for loc in ["fr-be", "fr-ch", "en"]:
        assert loc in result.localised_data["versions"]


def test_hreflang_contient_x_default(session_avec_locales):
    result = asyncio.run(run(session_avec_locales))
    assert "x-default" in result.localised_data["hreflang_tags"]


def test_resultat_stocke(session_avec_locales):
    result = asyncio.run(run(session_avec_locales))
    assert result.agent_results["agent_20"].data == result.localised_data


# ─── 4. Mock localisation ─────────────────────────────────────────────

def test_mock_produit_versions_pour_chaque_locale(session_avec_locales):
    loc = _mock_localisation(session_avec_locales)
    assert set(loc.versions.keys()) == {"fr-be", "fr-ch", "en"}


def test_mock_adapte_loi():
    session = SessionState(keyword="test", config=SessionConfig(
        target_locales=["fr-ch"]), brouillon_html="<p>droit francais</p>")
    loc = _mock_localisation(session)
    assert "droit suisse" in loc.versions.get("fr-ch", "")


# ─── 5. Build hreflang ────────────────────────────────────────────────

def test_build_hreflang():
    tags = _build_hreflang(["fr", "fr-be", "en"], "https://example.fr/article")
    assert 'hreflang="fr"' in tags
    assert 'hreflang="fr-be"' in tags
    assert 'hreflang="en"' in tags
    assert "x-default" in tags


def test_build_hreflang_vide():
    assert _build_hreflang([]) == ""


# ─── 6. LOCALE_ADAPTATIONS ────────────────────────────────────────────

def test_locales_connues():
    for loc in ["fr", "fr-be", "fr-ch", "fr-ca", "en", "en-gb", "de", "es", "it"]:
        assert loc in LOCALE_ADAPTATIONS, f"Locale {loc} manquant"


def test_locales_ont_tous_les_champs():
    for info in LOCALE_ADAPTATIONS.values():
        for field in ("devise", "loi", "fuseau", "separateur"):
            assert field in info


# ─── 7. JSON extraction ───────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"versions": {"fr": "ok"}}')["versions"] == {"fr": "ok"}


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
