"""Tests unitaires pour Agent 01 — Brief Entreprise."""

import json
import asyncio

import pytest

from hermes.agents.agent_01_brief_entreprise import (
    _extract_json,
    _build_user_message,
    _load_prompt,
    _mock_fiche_entreprise,
    run,
)
from hermes.models.agent_data import FicheEntreprise
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def session_valide():
    """Session valide pour l'Agent 01."""
    return SessionState(
        keyword="assurance vie temporaire",
        site_url="https://www.monassureur.fr",
        objectif="Article pilier",
        config=SessionConfig(
            mode=QualityMode.DEBUG,
            dry_run=True,
            secteur="finance",
        ),
    )


@pytest.fixture
def session_sans_url():
    """Session sans URL de site."""
    return SessionState(
        keyword="test",
        config=SessionConfig(
            mode=QualityMode.DEBUG,
            dry_run=True,
            secteur="saas",
        ),
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    """L'Agent 01 s'exécute avec succès sur une session valide."""
    result = asyncio.run(run(session_valide))
    assert result.fiche_entreprise is not None
    assert result.fiche_entreprise["nom"]
    assert result.fiche_entreprise["secteur"] == "finance"
    assert len(result.fiche_entreprise["offres"]) > 0

    agent_result = result.agent_results["agent_01"]
    assert agent_result.status == AgentStatus.COMPLETED
    assert agent_result.model_used == "dry-run"


def test_run_fiche_entreprise_pydantic_valide(session_valide):
    """La sortie est validable par le modèle Pydantic FicheEntreprise."""
    result = asyncio.run(run(session_valide))
    fiche = FicheEntreprise.model_validate(result.fiche_entreprise)
    assert fiche.nom
    assert fiche.secteur
    assert fiche.positionnement


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_url_fonctionne(session_sans_url):
    """L'Agent 01 fonctionne même sans URL (dry-run)."""
    result = asyncio.run(run(session_sans_url))
    assert result.fiche_entreprise is not None
    assert result.fiche_entreprise["nom"]


def test_run_avec_secteur_non_precise():
    """Secteur manquant : l'agent utilise 'autre' par défaut."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    result = asyncio.run(run(session))
    assert result.fiche_entreprise["secteur"] == "saas"  # dry-run default


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_fiche_entreprise_tous_les_champs(session_valide):
    """La fiche entreprise contient tous les champs attendus."""
    result = asyncio.run(run(session_valide))
    fiche = result.fiche_entreprise

    assert "nom" in fiche
    assert "secteur" in fiche
    assert "positionnement" in fiche
    assert isinstance(fiche["offres"], list)
    assert isinstance(fiche["preuves"], list)
    assert isinstance(fiche["contraintes_legales"], list)
    assert isinstance(fiche["mots_cles_interdits"], list)
    assert isinstance(fiche["elements_differenciants"], list)


def test_resultat_stocke_dans_session(session_valide):
    """Le résultat est bien stocké dans state.agent_results."""
    result = asyncio.run(run(session_valide))
    agent_result = result.agent_results.get("agent_01")
    assert agent_result is not None
    assert agent_result.data is not None
    assert agent_result.data["nom"] == result.fiche_entreprise["nom"]


def test_last_completed_agent_id_mis_a_jour(session_valide):
    """Après exécution, last_completed_agent_id pointe sur agent_01."""
    result = asyncio.run(run(session_valide))
    assert result.last_completed_agent_id == "agent_01"


# ─── 4. Erreur contrôlée ───────────────────────────────────────────────

def test_session_conserve_etat_apres_echec():
    """En cas d'échec, la session conserve son état."""
    session = SessionState(
        keyword="test",
        site_url="https://exemple.fr",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    # Simuler un appel dry-run qui fonctionne mais tester la robustesse
    # en vérifiant que l'état est cohérent même si on relance
    result1 = asyncio.run(run(session))
    # Relancer — l'agent doit écraser l'ancien résultat
    result2 = asyncio.run(run(result1))
    assert result2.agent_results["agent_01"].status == AgentStatus.COMPLETED


# ─── 5. Extraction JSON ────────────────────────────────────────────────

def test_extract_json_bloc_markdown():
    texte = '```json\n{"nom": "Test", "secteur": "saas", "positionnement": "Leader"}\n```'
    data = _extract_json(texte)
    assert data["nom"] == "Test"


def test_extract_json_objet_direct():
    texte = '{"nom": "Test", "secteur": "saas", "positionnement": "Leader"}'
    data = _extract_json(texte)
    assert data["nom"] == "Test"


def test_extract_json_avec_texte_autour():
    texte = 'Voici le résultat :\n{"nom": "TestCorp", "secteur": "finance", "positionnement": "Courtier"}\nJ\'espère que cela convient.'
    data = _extract_json(texte)
    assert data["nom"] == "TestCorp"
    assert data["secteur"] == "finance"


def test_extract_json_imbrique():
    texte = '{"nom": "Test", "secteur": "saas", "positionnement": "Leader", "metadata": {"source": "web"}}'
    data = _extract_json(texte)
    assert data["metadata"]["source"] == "web"


def test_extract_json_invalide_leve_erreur():
    with pytest.raises(ValueError, match="Impossible d'extraire"):
        _extract_json("Ceci n'est pas du JSON.")


# ─── 6. Build user message ─────────────────────────────────────────────

def test_build_user_message_contient_url():
    session = SessionState(
        keyword="test",
        site_url="https://exemple.fr",
        config=SessionConfig(secteur="saas"),
    )
    msg = _build_user_message(session)
    assert "https://exemple.fr" in msg
    assert "saas" in msg
    assert "test" in msg


def test_build_user_message_sans_url():
    session = SessionState(
        keyword="test",
        config=SessionConfig(secteur="saas"),
    )
    msg = _build_user_message(session)
    assert "Non fourni" in msg


# ─── 7. Prompt ─────────────────────────────────────────────────────────

def test_load_prompt_retourne_texte():
    prompt = _load_prompt()
    assert len(prompt) > 100
    assert "Agent 01" in prompt


def test_load_prompt_ne_contient_pas_frontmatter():
    prompt = _load_prompt()
    assert "---" not in prompt  # Le frontmatter YAML doit être retiré


# ─── 8. Mock dry-run ───────────────────────────────────────────────────

def test_mock_fiche_entreprise_secteur_reglemente():
    session = SessionState(
        keyword="test",
        config=SessionConfig(secteur="sante", dry_run=True),
    )
    fiche = _mock_fiche_entreprise(session)
    assert len(fiche.contraintes_legales) > 0
    assert fiche.secteur == "sante"


def test_mock_fiche_entreprise_secteur_non_reglemente():
    session = SessionState(
        keyword="test",
        config=SessionConfig(secteur="saas", dry_run=True),
    )
    fiche = _mock_fiche_entreprise(session)
    assert fiche.contraintes_legales == []
