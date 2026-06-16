"""Tests unitaires pour Agent 09 — Redaction."""

import asyncio

import pytest

from hermes.agents.agent_09_redaction import (
    _build_system_prompt, _build_user_message, _extract_json,
    _extract_html, _mock_brouillon, run, compter_mots,
)
from hermes.models.agent_data import Brouillon
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_pilier():
    """Session complete pour un article pilier."""
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        site_url="https://www.monassureur.fr",
        objectif="Informer sur l'assurance vie temporaire et generer des leads qualifies",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={
            "nom": "MonAssureur", "secteur": "finance",
            "positionnement": "Courtier 100% digital, simple et transparent",
            "offres": ["Assurance vie temporaire", "Assurance vie permanente", "Assurance deces"],
            "ton_marque": "Professionnel rassurant, accessible, sans jargon inutile",
            "preuves": ["Agree AMF", "100 000 clients", "Application mobile 4.8/5"],
            "contraintes_legales": ["Mention 'Ce produit presente un risque de perte en capital'",
                                     "Avertissement fiscal"],
            "mots_cles_interdits": ["gratuit", "sans risque", "placement garanti"],
            "elements_differenciants": ["Souscription 100% en ligne", "Comparateur integre"],
        },
        fiche_persona={
            "nom_persona": "Paul 45 ans", "maturite": "intermediaire",
            "vocabulaire_recommande": ["prime", "capital", "beneficiaire", "quotite", "terme"],
            "canal_acquisition": "search",
            "objectif_lecture": "Comprendre les options avant d'acheter une assurance vie",
            "freins": ["Peur de perdre son capital", "Trop de jargon", "Difficulte a comparer"],
            "questions_typiques": ["Quelle difference entre temporaire et permanente ?",
                                    "Comment est calculee la prime ?"],
            "niveau_expertise": "intermediaire",
        },
        serp_data={
            "top10": [
                {"position": 1, "title": "Guide assurance vie", "url": "https://test.fr",
                 "snippet": "...", "domain": "test.fr"},
            ],
            "paa": ["Qu'est-ce que l'assurance vie temporaire ?",
                     "Comment fonctionne l'assurance vie temporaire ?",
                     "Quel est le prix d'une assurance vie temporaire ?",
                     "Comment choisir la bonne quotite ?",
                     "Quelle duree choisir ?"],
            "concurrents_directs": ["assurland.com", "meilleurtaux.com", "lesfurets.com"],
            "ai_overviews": [{"content": "L'assurance vie temporaire protege vos proches..."}],
        },
        intention="informative",
        type_page="pilier",
        offre_conversion_data={
            "benefices": ["Protegez vos proches", "Des primes jusqu'a 40% moins cheres",
                          "Souscription 100% en ligne en 15 minutes"],
            "objections": ["Mon capital est-il vraiment protege ?",
                           "Les demarches sont-elles compliquees ?",
                           "Le prix est-il justifie ?"],
            "preuves": ["Agree AMF", "100 000 clients proteges", "Note 4.8/5 sur Trustpilot"],
            "cta_principal": "Demandez votre devis gratuit en 2 minutes",
            "cta_secondaire": "Telechargez notre guide complet",
            "valeur_ajoutee_unique": "La seule assurance vie temporaire 100% digitale "
                                     "avec comparateur de prix integre",
        },
        angles_differenciants={
            "angles_faibles": ["Pas de guide exhaustif a jour en 2026",
                               "Manque de donnees chiffrees chez les concurrents",
                               "Absence d'exemples concrets de calcul de prime"],
            "opportunites_uniques": ["Creer le guide le plus complet du marche",
                                      "Inclure un tableau comparatif des garanties",
                                      "Ajouter un calculateur de prime integre"],
            "angle_principal": "Guide exhaustif et transparent avec donnees verificables",
            "facteurs_differenciation": ["Comparateur integre", "Donnees exclusives"],
        },
        template_data={
            "template_id": "pilier",
            "structure": [
                {"type": "h1", "titre": "Guide complet assurance vie temporaire",
                 "contenu_guide": "Titre exhaustif", "obligatoire": True, "ordre": 0},
                {"type": "intro", "titre": "Introduction",
                 "contenu_guide": "Pourquoi ce guide existe", "obligatoire": True, "ordre": 1},
                {"type": "h2", "titre": "Definition et principes cles",
                 "contenu_guide": "Definir le sujet", "obligatoire": True, "ordre": 2},
                {"type": "h2", "titre": "Comment ca fonctionne",
                 "contenu_guide": "Mecanisme et etapes", "obligatoire": True, "ordre": 3},
                {"type": "h2", "titre": "FAQ",
                 "contenu_guide": "5 questions/reponses", "obligatoire": True, "ordre": 4},
                {"type": "conclusion", "titre": "Conclusion",
                 "contenu_guide": "Synthese + CTA", "obligatoire": True, "ordre": 5},
            ],
            "nb_sections": 6,
        },
        anti_cannib_data={"conflit_detecte": False, "action": "proceed"},
        agent_results={
            f"agent_{i:02d}": AgentResult(agent_id=f"agent_{i:02d}", status=AgentStatus.COMPLETED)
            for i in range(1, 9)
        },
    )


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert result.brouillon_html is not None
    assert len(result.brouillon_html) > 500
    assert result.agent_results["agent_09"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_pilier):
    result = asyncio.run(run(session_pilier))
    data = result.agent_results["agent_09"].data
    brouillon = Brouillon.model_validate(data)
    assert brouillon.html
    assert brouillon.word_count > 0
    assert brouillon.titre


def test_html_contient_h1(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert "<h1" in result.brouillon_html.lower()


def test_html_contient_h2(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert "<h2" in result.brouillon_html.lower()


def test_html_pas_de_css_inline(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert "style=" not in result.brouillon_html


def test_html_pas_de_javascript(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert "<script" not in result.brouillon_html.lower()


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_avec_session_minimale():
    session = SessionState(
        keyword="test minimal",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    result = asyncio.run(run(session))
    assert result.brouillon_html
    assert result.agent_results["agent_09"].status == AgentStatus.COMPLETED


def test_run_sans_template():
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        type_page="article",
    )
    result = asyncio.run(run(session))
    assert result.brouillon_html


def test_run_keyword_vide():
    session = SessionState(
        keyword="",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    result = asyncio.run(run(session))
    assert result.brouillon_html


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_brouillon_tous_les_champs(session_pilier):
    result = asyncio.run(run(session_pilier))
    data = result.agent_results["agent_09"].data
    for field in ("html", "word_count", "titre", "meta_description", "sections"):
        assert field in data, f"Champ manquant: {field}"


def test_word_count_positif(session_pilier):
    result = asyncio.run(run(session_pilier))
    data = result.agent_results["agent_09"].data
    assert data["word_count"] > 0


def test_meta_description_longueur(session_pilier):
    result = asyncio.run(run(session_pilier))
    meta = result.agent_results["agent_09"].data["meta_description"]
    assert 50 <= len(meta) <= 200


def test_resultat_stocke(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert result.brouillon_html == result.agent_results["agent_09"].data["html"]


def test_last_completed_agent_id(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert result.last_completed_agent_id == "agent_09"


# ─── 4. Build system prompt ────────────────────────────────────────────

def test_system_prompt_contient_entreprise(session_pilier):
    prompt = _build_system_prompt(session_pilier)
    assert "MonAssureur" in prompt
    assert "Paul 45 ans" in prompt


def test_system_prompt_contient_mots_interdits(session_pilier):
    prompt = _build_system_prompt(session_pilier)
    assert "gratuit" in prompt


def test_system_prompt_contient_contraintes_legales(session_pilier):
    prompt = _build_system_prompt(session_pilier)
    assert "risque de perte" in prompt


def test_system_prompt_contient_cta(session_pilier):
    prompt = _build_system_prompt(session_pilier)
    assert "devis gratuit" in prompt.lower()


def test_system_prompt_contient_structure(session_pilier):
    prompt = _build_system_prompt(session_pilier)
    assert "h2" in prompt.lower()


def test_system_prompt_sans_valeurs_sectionnelles():
    """Meme sans certaines sections, le prompt ne plante pas."""
    session = SessionState(keyword="test")
    prompt = _build_system_prompt(session)
    assert len(prompt) > 100


# ─── 5. Build user message ─────────────────────────────────────────────

def test_user_message_contient_keyword(session_pilier):
    msg = _build_user_message(session_pilier)
    assert "assurance vie temporaire" in msg


def test_user_message_contient_type_page(session_pilier):
    msg = _build_user_message(session_pilier)
    assert "pilier" in msg


# ─── 6. Extraction HTML ────────────────────────────────────────────────

def test_extract_html_detecte_balises():
    html = _extract_html("<h1>Mon Titre</h1><p>Un paragraphe assez long pour depasser les 100 caracteres minimum requis par la fonction d'extraction HTML. " + "x" * 50 + "</p>")
    assert "Mon Titre" in html


def test_extract_html_pas_de_html():
    assert _extract_html("Pas de HTML ici.") == ""


# ─── 7. Mock dry-run ───────────────────────────────────────────────────

def test_mock_brouillon_contient_keyword(session_pilier):
    brouillon = _mock_brouillon(session_pilier)
    assert "assurance vie temporaire" in brouillon.html.lower()


def test_mock_brouillon_word_count():
    session = SessionState(keyword="test", config=SessionConfig(dry_run=True))
    brouillon = _mock_brouillon(session)
    assert brouillon.word_count > 0
    assert brouillon.word_count == compter_mots(brouillon.html)


def test_mock_brouillon_a_des_sections():
    session = SessionState(keyword="test", config=SessionConfig(dry_run=True))
    brouillon = _mock_brouillon(session)
    assert len(brouillon.sections) > 0


# ─── 8. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    data = _extract_json('{"html": "<h1>Test</h1>", "word_count": 5}')
    assert data["html"] == "<h1>Test</h1>"


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
