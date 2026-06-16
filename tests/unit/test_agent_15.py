"""Tests unitaires pour Agent 15 — Fact-checking."""

import asyncio

import pytest

from hermes.agents.agent_15_fact_checking import (
    _extract_facts, _check_internal_consistency, _score_fiabilite,
    _strip_html, _build_user_message, _extract_json, run,
)
from hermes.models.agent_data import ErreurFactuelle, FactCheckData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        brouillon_html=(
            "<h1>Guide Assurance Vie</h1>"
            "<p>Selon la Federation Francaise de l'Assurance, "
            "plus de 10 millions de Francais sont couverts par une assurance vie en 2025.</p>"
            "<p>Le taux moyen est de 3.5% en 2026.</p>"
            "<p>Notre solution est la meilleure du marche.</p>"
            "<p>Cette methode fonctionne toujours, sans exception.</p>"
        ),
        agent_results={
            "agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED),
        },
    )


@pytest.fixture
def session_correcte():
    return SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        brouillon_html=(
            "<h1>Information</h1>"
            "<p>En 2025, le marche a progresse de 12% selon l'INSEE.</p>"
            "<p>Source : INSEE, rapport annuel 2025. Derniere mise a jour : janvier 2026.</p>"
        ),
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.fact_check_data is not None
    assert 0 <= result.fact_check_data["score_fiabilite"] <= 10
    assert result.agent_results["agent_15"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    FactCheckData.model_validate(result.fact_check_data)


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.fact_check_data is not None


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_factcheck_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    for field in ("erreurs", "corrections", "score_fiabilite", "sources_verifiees"):
        assert field in result.fact_check_data, f"Champ manquant: {field}"


def test_score_fiabilite_dans_limites(session_valide):
    result = asyncio.run(run(session_valide))
    assert 0 <= result.fact_check_data["score_fiabilite"] <= 10


def test_erreurs_format_valide(session_valide):
    result = asyncio.run(run(session_valide))
    for e in result.fact_check_data["erreurs"]:
        assert "gravite" in e
        assert e["gravite"] in ("mineure", "moderee", "majeure", "critique")


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_15"].data == result.fact_check_data


# ─── 4. Extraction de faits ────────────────────────────────────────────

def test_extract_facts_chiffres(session_valide):
    text = _strip_html(session_valide.brouillon_html or "")
    facts = _extract_facts(text)
    types = {f["type"] for f in facts}
    assert len(facts) > 0


def test_extract_facts_superlatif():
    facts = _extract_facts("Notre produit est le meilleur du marche et le numero 1 en France.")
    types = {f["type"] for f in facts}
    assert "superlatif (drapeau rouge)" in types


def test_extract_facts_affirmation_absolue():
    facts = _extract_facts("Cette methode fonctionne toujours, sans aucune exception.")
    types = {f["type"] for f in facts}
    assert "affirmation absolue (drapeau rouge)" in types


def test_extract_facts_annee():
    facts = _extract_facts("En 2025, le marche a progresse. Les donnees 2024 confirment.")
    types = {f["type"] for f in facts}
    assert "annee" in types


def test_extract_facts_montant():
    facts = _extract_facts("Le prix est de 150 euros par mois, soit 1 800 euros par an.")
    types = {f["type"] for f in facts}
    assert "chiffre/montant" in types

def test_extract_facts_vide():
    facts = _extract_facts("Un contenu ordinaire sans information particuliere.")
    assert facts == []


# ─── 5. Detection incoherences ────────────────────────────────────────

def test_check_consistency_date_future():
    facts = [{"texte": "2099", "type": "annee", "contexte": "En 2099, le produit sera lance."}]
    erreurs = _check_internal_consistency(facts)
    assert len(erreurs) > 0
    assert any("futur" in e.correction.lower() for e in erreurs)


def test_check_superlatif_genere_erreur():
    facts = [{"texte": "le meilleur", "type": "superlatif (drapeau rouge)",
              "contexte": "Notre produit est le meilleur."}]
    erreurs = _check_internal_consistency(facts)
    assert any("superlatif" in e.correction.lower() for e in erreurs)


def test_check_absolu_genere_erreur():
    facts = [{"texte": "toujours", "type": "affirmation absolue (drapeau rouge)",
              "contexte": "Cela fonctionne toujours."}]
    erreurs = _check_internal_consistency(facts)
    assert any("absolue" in e.correction.lower() for e in erreurs)


# ─── 6. Score fiabilite ────────────────────────────────────────────────

def test_score_perfect():
    assert _score_fiabilite([], 5) == 10


def test_score_critique_chute():
    erreurs = [ErreurFactuelle(gravite="critique")]
    assert _score_fiabilite(erreurs, 0) == 0


def test_score_bonus_beaucoup_de_faits():
    erreurs: list = []
    assert _score_fiabilite(erreurs, 15) == 10  # capped


# ─── 7. Strip HTML ─────────────────────────────────────────────────────

def test_strip_html():
    text = _strip_html("<h1>Titre</h1><p>Paragraphe.</p>")
    assert "Titre" in text


# ─── 8. Build user message ─────────────────────────────────────────────

def test_build_message(session_valide):
    text = _strip_html(session_valide.brouillon_html or "")
    facts = _extract_facts(text)
    msg = _build_user_message(session_valide, text, facts)
    assert "score_fiabilite" in msg


# ─── 9. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"score_fiabilite": 8}')["score_fiabilite"] == 8
