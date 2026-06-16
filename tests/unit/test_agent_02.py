"""Tests unitaires pour Agent 02 — Persona / Lecteur cible."""

import asyncio

import pytest

from hermes.agents.agent_02_persona import (
    _extract_json,
    _build_user_message,
    _load_prompt,
    _mock_persona,
    run,
)
from hermes.models.agent_data import FichePersona
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def session_valide():
    return SessionState(
        keyword="assurance vie temporaire",
        site_url="https://www.monassureur.fr",
        objectif="Article pilier pour informer les prospects",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={
            "nom": "MonAssureur",
            "secteur": "finance",
            "positionnement": "Courtier en assurance 100% digital",
            "offres": ["Assurance vie temporaire", "Assurance vie permanente"],
            "ton_marque": "Professionnel et rassurant",
            "preuves": ["Agréé AMF", "100 000 clients"],
            "contraintes_legales": ["Mentions légales assurance"],
            "mots_cles_interdits": ["gratuit"],
            "elements_differenciants": ["Souscription en ligne", "Comparateur intégré"],
        },
        agent_results={
            "agent_01": AgentResult(
                agent_id="agent_01", agent_name="Brief", status=AgentStatus.COMPLETED,
            ),
        },
    )


@pytest.fixture
def session_sans_entreprise():
    return SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="saas"),
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.fiche_persona is not None
    assert result.fiche_persona["nom_persona"]
    assert result.fiche_persona["maturite"] in ("debutant", "intermediaire", "expert")
    agent_result = result.agent_results["agent_02"]
    assert agent_result.status == AgentStatus.COMPLETED


def test_run_persona_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    persona = FichePersona.model_validate(result.fiche_persona)
    assert persona.nom_persona
    assert persona.niveau_expertise in ("debutant", "intermediaire", "expert")


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_fiche_entreprise(session_sans_entreprise):
    result = asyncio.run(run(session_sans_entreprise))
    assert result.fiche_persona is not None
    assert result.fiche_persona["nom_persona"]


def test_run_secteur_saas_generique(session_sans_entreprise):
    result = asyncio.run(run(session_sans_entreprise))
    assert result.agent_results["agent_02"].status == AgentStatus.COMPLETED


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_fiche_persona_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    persona = result.fiche_persona
    assert "nom_persona" in persona
    assert "maturite" in persona
    assert isinstance(persona["vocabulaire_recommande"], list)
    assert len(persona["vocabulaire_recommande"]) > 0
    assert isinstance(persona["freins"], list)
    assert isinstance(persona["questions_typiques"], list)
    assert len(persona["questions_typiques"]) > 0


def test_canal_acquisition_valide(session_valide):
    result = asyncio.run(run(session_valide))
    canal = result.fiche_persona["canal_acquisition"]
    assert canal in ("search", "social", "email", "direct", "")


def test_resultat_stocke_dans_session(session_valide):
    result = asyncio.run(run(session_valide))
    agent_result = result.agent_results.get("agent_02")
    assert agent_result is not None
    assert agent_result.data == result.fiche_persona


def test_last_completed_agent_id(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.last_completed_agent_id == "agent_02"


# ─── 4. Erreur contrôlée ───────────────────────────────────────────────

def test_relance_ecrase_ancien_resultat(session_valide):
    result1 = asyncio.run(run(session_valide))
    first_name = result1.fiche_persona["nom_persona"]
    result2 = asyncio.run(run(result1))
    assert result2.agent_results["agent_02"].status == AgentStatus.COMPLETED
    assert result2.fiche_persona["nom_persona"] == first_name  # dry-run déterministe


# ─── 5. Extraction JSON ────────────────────────────────────────────────

def test_extract_json_valide():
    texte = '{"nom_persona": "Paul", "maturite": "intermediaire"}'
    data = _extract_json(texte)
    assert data["nom_persona"] == "Paul"


def test_extract_json_bloc_markdown():
    texte = '```json\n{"nom_persona": "Marie", "maturite": "expert"}\n```'
    data = _extract_json(texte)
    assert data["maturite"] == "expert"


def test_extract_json_invalide():
    with pytest.raises(ValueError):
        _extract_json("Pas de JSON ici.")


# ─── 6. Build user message ─────────────────────────────────────────────

def test_build_user_message_contient_entreprise(session_valide):
    msg = _build_user_message(session_valide)
    assert "MonAssureur" in msg
    assert "assurance vie temporaire" in msg


def test_build_user_message_sans_fiche(session_sans_entreprise):
    msg = _build_user_message(session_sans_entreprise)
    assert "test" in msg
    assert "Non précisé" in msg


# ─── 7. Prompt ─────────────────────────────────────────────────────────

def test_load_prompt_retourne_texte():
    prompt = _load_prompt()
    assert len(prompt) > 100
    assert "persona" in prompt.lower() or "Agent 02" in prompt


# ─── 8. Mock dry-run ───────────────────────────────────────────────────

def test_mock_persona_finance(session_valide):
    persona = _mock_persona(session_valide)
    assert "rendement" in persona.vocabulaire_recommande
    assert persona.canal_acquisition == "search"


def test_mock_persona_saas():
    session = SessionState(
        keyword="logiciel crm",
        config=SessionConfig(secteur="saas"),
    )
    persona = _mock_persona(session)
    assert persona.nom_persona
    assert len(persona.questions_typiques) >= 3
    assert persona.maturite == "intermediaire"


def test_mock_persona_sante():
    session = SessionState(
        keyword="traitement migraine",
        config=SessionConfig(secteur="sante"),
    )
    persona = _mock_persona(session)
    assert "symptôme" in persona.vocabulaire_recommande or "traitement" in persona.vocabulaire_recommande
    assert persona.maturite == "debutant"
