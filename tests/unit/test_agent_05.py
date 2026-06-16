"""Tests unitaires pour Agent 05 — Offre & Conversion."""

import asyncio

import pytest

from hermes.agents.agent_05_offre_conversion import (
    _extract_json, _build_user_message, _mock_offre, run,
)
from hermes.models.agent_data import OffreConversion
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="acheter assurance vie temporaire",
        site_url="https://www.monassureur.fr",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={
            "nom": "MonAssureur", "secteur": "finance",
            "positionnement": "Courtier 100% digital",
            "offres": ["Assurance vie temporaire", "Assurance permanente"],
            "ton_marque": "Professionnel rassurant",
            "preuves": ["Agree AMF", "100 000 clients", "Application mobile 4.8"],
            "elements_differenciants": ["Souscription 100% en ligne", "Comparateur integre"],
        },
        fiche_persona={
            "nom_persona": "Paul 45 ans", "maturite": "intermediaire",
            "freins": ["Peur de perdre son capital", "Trop de jargon financier",
                        "Difficulte a comparer les offres"],
            "objectif_lecture": "Comprendre les options avant d'acheter",
        },
        intention="transactionnelle",
        type_page="landing",
        agent_results={
            "agent_01": AgentResult(agent_id="agent_01", status=AgentStatus.COMPLETED),
            "agent_02": AgentResult(agent_id="agent_02", status=AgentStatus.COMPLETED),
            "agent_04": AgentResult(agent_id="agent_04", status=AgentStatus.COMPLETED),
        },
    )


@pytest.fixture
def session_informative():
    return SessionState(
        keyword="comment fonctionne l'assurance vie",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={"nom": "MonAssureur", "secteur": "finance",
                          "positionnement": "Courtier digital",
                          "offres": ["Assurance vie"]},
        intention="informative",
        agent_results={
            "agent_01": AgentResult(agent_id="agent_01", status=AgentStatus.COMPLETED),
            "agent_02": AgentResult(agent_id="agent_02", status=AgentStatus.SKIPPED_USER),
            "agent_04": AgentResult(agent_id="agent_04", status=AgentStatus.COMPLETED),
        },
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.offre_conversion_data is not None
    assert len(result.offre_conversion_data["benefices"]) >= 1
    assert result.offre_conversion_data["cta_principal"]
    assert result.agent_results["agent_05"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    offre = OffreConversion.model_validate(result.offre_conversion_data)
    assert offre.cta_principal


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_persona(session_informative):
    result = asyncio.run(run(session_informative))
    assert result.offre_conversion_data is not None
    assert result.agent_results["agent_05"].status == AgentStatus.COMPLETED


def test_run_minimal():
    session = SessionState(
        keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    result = asyncio.run(run(session))
    assert result.offre_conversion_data["cta_principal"]


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_offre_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    data = result.offre_conversion_data
    for field in ("benefices", "objections", "preuves", "cta_principal",
                  "cta_secondaire", "valeur_ajoutee_unique"):
        assert field in data, f"Champ manquant: {field}"


def test_benefices_sont_liste(session_valide):
    result = asyncio.run(run(session_valide))
    assert isinstance(result.offre_conversion_data["benefices"], list)
    assert len(result.offre_conversion_data["benefices"]) >= 1


def test_objections_sont_liste(session_valide):
    result = asyncio.run(run(session_valide))
    assert isinstance(result.offre_conversion_data["objections"], list)


def test_cta_adapte_intention_transactionnelle(session_valide):
    result = asyncio.run(run(session_valide))
    cta = result.offre_conversion_data["cta_principal"].lower()
    assert any(t in cta for t in ("devis", "essai", "achet", "souscri", "gratuit", "demand"))


def test_cta_adapte_intention_informative(session_informative):
    result = asyncio.run(run(session_informative))
    cta = result.offre_conversion_data["cta_principal"].lower()
    assert any(t in cta for t in ("guide", "telecharg", "newsletter", "expert", "contact"))


# ─── 4. Erreur contrôlée ───────────────────────────────────────────────

def test_relance_ecrase_ancien_resultat(session_valide):
    result1 = asyncio.run(run(session_valide))
    first_cta = result1.offre_conversion_data["cta_principal"]
    result2 = asyncio.run(run(result1))
    assert result2.agent_results["agent_05"].status == AgentStatus.COMPLETED


# ─── 5. Extraction JSON ────────────────────────────────────────────────

def test_extract_json_valide():
    data = _extract_json('{"benefices": ["b1"], "cta_principal": "test"}')
    assert data["benefices"] == ["b1"]


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}


# ─── 6. Build user message ─────────────────────────────────────────────

def test_build_message_contient_entreprise_persona(session_valide):
    msg = _build_user_message(session_valide)
    assert "MonAssureur" in msg
    assert "Paul 45 ans" in msg


# ─── 7. Mock dry-run ───────────────────────────────────────────────────

def test_mock_offre_utilise_preuves_entreprise(session_valide):
    offre = _mock_offre(session_valide)
    assert any("AMF" in p or "100" in p for p in offre.preuves)


def test_mock_offre_cta_transactionnel(session_valide):
    offre = _mock_offre(session_valide)
    assert offre.cta_principal


def test_mock_offre_vau_utilise_differenciants(session_valide):
    offre = _mock_offre(session_valide)
    assert offre.valeur_ajoutee_unique


def test_mock_offre_fallbacks_sans_donnees():
    session = SessionState(keyword="test", config=SessionConfig(dry_run=True))
    offre = _mock_offre(session)
    assert offre.benefices
    assert offre.objections
    assert offre.preuves
    assert offre.cta_principal
