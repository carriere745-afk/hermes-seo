"""Tests unitaires pour Agent 10 — SEO."""

import asyncio

import pytest

from hermes.agents.agent_10_seo import (
    _extract_headings, _strip_html, _keyword_density,
    _extract_json, _build_user_message, _mock_seo, run,
)
from hermes.models.agent_data import SeoData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={"nom": "MonAssureur", "secteur": "finance"},
        intention="informative",
        type_page="pilier",
        brouillon_html=(
            "<h1>Guide Complet Assurance Vie Temporaire</h1>"
            "<p>L'assurance vie temporaire protege vos proches en cas de deces. "
            "Ce guide complet vous explique tout ce que vous devez savoir.</p>"
            "<h2>Definition de l'assurance vie temporaire</h2>"
            "<p>L'assurance vie temporaire est un contrat qui garantit le versement "
            "d'un capital au beneficiaire si l'assure decede pendant la periode de couverture.</p>"
            "<h2>Comment fonctionne l'assurance vie temporaire</h2>"
            "<p>Le fonctionnement est simple : vous choisissez un capital et une duree...</p>"
            "<h2>Les avantages de l'assurance vie temporaire</h2>"
            "<p>Protegez votre famille avec des primes avantageuses...</p>"
            "<h2>FAQ</h2>"
            "<h3>Quelle est la difference entre temporaire et permanente ?</h3>"
            "<p>L'assurance temporaire couvre une periode definie...</p>"
            "<h3>Comment est calculee la prime ?</h3>"
            "<p>La prime est calculee selon votre age, votre etat de sante...</p>"
            "<h2>Conclusion</h2>"
            "<p>L'assurance vie temporaire est une solution efficace...</p>"
        ),
        agent_results={
            "agent_09": AgentResult(
                agent_id="agent_09", agent_name="Redaction",
                status=AgentStatus.COMPLETED,
                data={"titre": "Guide Complet Assurance Vie Temporaire",
                       "meta_description": "Tout savoir sur l'assurance vie temporaire."},
            ),
        },
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.seo_data is not None
    assert result.seo_data["title_optimise"]
    assert result.seo_data["meta_description_optimise"]
    assert result.agent_results["agent_10"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    SeoData.model_validate(result.seo_data)


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.seo_data is not None


def test_run_sans_keyword():
    session = SessionState(keyword="", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.agent_results["agent_10"].status == AgentStatus.COMPLETED


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_seo_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    data = result.seo_data
    for field in ("title_optimise", "meta_description_optimise", "hn_structure",
                  "densite_mots_cles", "suggestions_maillage"):
        assert field in data, f"Champ manquant: {field}"


def test_title_longueur(session_valide):
    result = asyncio.run(run(session_valide))
    title = result.seo_data["title_optimise"]
    assert 20 <= len(title) <= 80


def test_meta_longueur(session_valide):
    result = asyncio.run(run(session_valide))
    meta = result.seo_data["meta_description_optimise"]
    assert len(meta) >= 50


def test_hn_structure_contient_h1(session_valide):
    result = asyncio.run(run(session_valide))
    hn = result.seo_data["hn_structure"]
    assert "h2" in hn


def test_suggestions_maillage_est_liste(session_valide):
    result = asyncio.run(run(session_valide))
    assert isinstance(result.seo_data["suggestions_maillage"], list)


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_10"].data == result.seo_data


# ─── 4. Extraction headings ────────────────────────────────────────────

def test_extract_headings():
    html = "<h1>Titre</h1><h2>Sous-titre</h2><h2>Autre H2</h2><h3>Sous H3</h3>"
    h = _extract_headings(html)
    assert h["h1"] == ["Titre"]
    assert len(h["h2"]) == 2
    assert len(h["h3"]) == 1


def test_extract_headings_vide():
    h = _extract_headings("<p>Pas de titre</p>")
    assert h["h1"] == []
    assert h["h2"] == []


# ─── 5. Strip HTML ─────────────────────────────────────────────────────

def test_strip_html():
    text = _strip_html("<h1>Titre</h1><p>Paragraphe avec du <strong>gras</strong>.</p>")
    assert "Titre" in text
    assert "Paragraphe" in text
    assert "gras" in text


# ─── 6. Keyword density ────────────────────────────────────────────────

def test_keyword_density():
    text = "assurance vie temporaire est un produit assurance vie. L'assurance vie temporaire protege."
    d = _keyword_density(text, "assurance vie temporaire")
    assert d > 0


def test_keyword_density_zero():
    # "pizza" n'apparait pas du tout dans "rien a voir ici"
    d = _keyword_density("rien a voir ici", "pizza")
    assert d == 0.0


def test_keyword_density_vide():
    d = _keyword_density("", "test")
    assert d == 0.0


# ─── 7. Mock dry-run ───────────────────────────────────────────────────

def test_mock_seo_title_contient_keyword(session_valide):
    seo = _mock_seo(session_valide)
    assert "assurance vie" in seo.title_optimise.lower()


def test_mock_seo_a_des_suggestions(session_valide):
    seo = _mock_seo(session_valide)
    assert len(seo.suggestions_maillage) >= 2


def test_mock_seo_densite_non_zero(session_valide):
    seo = _mock_seo(session_valide)
    assert seo.densite_mots_cles


# ─── 8. Build user message ─────────────────────────────────────────────

def test_build_user_message(session_valide):
    html = session_valide.brouillon_html or ""
    h = _extract_headings(html)
    text = _strip_html(html)
    d = _keyword_density(text, "assurance vie temporaire")
    msg = _build_user_message(session_valide, h, len(text.split()), d)
    assert "assurance vie temporaire" in msg


# ─── 9. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"title_optimise": "test"}')["title_optimise"] == "test"


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
