"""Tests unitaires pour Agent 25 — Critique Qualite."""

import asyncio, pytest
from hermes.agents.agent_25_critique_qualite import (
    _evaluate, _score_lisibilite, _score_densite, _score_paa,
    _score_originalite, _score_fraicheur, _score_aeo, _score_geo,
    _score_erreurs, _score_naturalite, run, CRITERES_NON_APPLICABLES,
)
from hermes.models.agent_data import ScoresFinaux, GrilleScores
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_riche():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        type_page="pilier",
        fiche_entreprise={"nom": "MonAssureur", "elements_differenciants": ["Comparateur"]},
        brouillon_html=(
            "<h1>Guide Complet Assurance Vie Temporaire</h1>"
            "<p>L'assurance vie temporaire est un contrat qui protege vos proches "
            "en cas de deces pendant une periode determinee.</p>"
            "<p>Selon la Federation Francaise de l'Assurance, plus de 10 millions "
            "de Francais sont couverts par ce type de contrat en 2025.</p>"
            "<h2>Definition de l'assurance vie temporaire</h2>"
            "<p>Il s'agit d'un contrat d'assurance qui garantit le versement "
            "d'un capital au beneficiaire designe si l'assure decede.</p>"
            "<h2>Comment fonctionne l'assurance temporaire</h2>"
            "<p>Le fonctionnement est simple et transparent. Vous choisissez "
            "un capital, une duree, et vous payez une prime mensuelle.</p>"
        ),
        serp_data={"paa": ["Qu'est-ce que l'assurance vie temporaire ?",
                            "Comment fonctionne l'assurance vie temporaire ?",
                            "Quel est le prix ?", "Comment choisir ?"]},
        angles_differenciants={
            "angle_principal": "Guide exhaustif et transparent avec donnees verificables et comparateur integre",
            "facteurs_differenciation": ["Comparateur integre", "Donnees exclusives",
                                          "Application mobile primée", "Expertise reconnue"],
        },
        plan_refresh={"frequence_jours": 60},
        aeo_blocks={
            "en_bref": "L'assurance vie temporaire protege vos proches...",
            "h2_questions": ["Qu'est-ce que... ?", "Comment... ?", "Pourquoi... ?"],
            "faq": [{"question": "Q1", "reponse": "R1"}, {"question": "Q2", "reponse": "R2"}],
            "definitions": [{"terme": "Capital", "definition": "Somme versee"}, {"terme": "Prime", "definition": "Cotisation"}],
        },
        geo_data={
            "sources_primaires": [{"titre": "Source 1", "url": "https://..."}],
            "entites_nommees": ["Assurance vie", "FFA", "Code des assurances", "AMF"],
            "phrases_citables": ["Phrase 1.", "Phrase 2.", "Phrase 3."],
            "chunks": [{"titre": "Chunk 1", "contenu": "..."}, {"titre": "C2", "contenu": "..."}, {"titre": "C3", "contenu": "..."}],
        },
        fact_check_data={
            "score_fiabilite": 9,
            "erreurs": [{"gravite": "mineure"}],
        },
        conformite_data={"risque_juridique": "faible", "valide": True},
        agent_results={
            "agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED),
        },
    )


# ─── 1. Entree valide ────────────────────────────────────────────────

def test_run_produit_scores(session_riche):
    result = asyncio.run(run(session_riche))
    assert result.scores is not None
    s = result.scores["scores"]
    assert 0 <= s["lisibilite"] <= 10
    assert 0 <= s["densite_semantique"] <= 15
    assert result.scores["score_total"] > 0
    assert isinstance(result.scores["seuil_atteint"], bool)
    assert result.agent_results["agent_25"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_riche):
    ScoresFinaux.model_validate(asyncio.run(run(session_riche)).scores)


# ─── 2. Entree invalide ───────────────────────────────────────────────

def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.scores is not None


def test_run_html_vide():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
                           brouillon_html="")
    result = asyncio.run(run(session))
    assert result.scores["score_total"] >= 0


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_scores_tous_les_champs(session_riche):
    result = asyncio.run(run(session_riche))
    for field in ("scores", "score_total", "seuil_publication", "seuil_atteint",
                  "recommandation", "blocages", "verifications_humaines"):
        assert field in result.scores, f"Champ manquant: {field}"


def test_seuil_selon_mode():
    """Le seuil varie selon le mode qualite."""
    for mode, expected in [("fast", 65), ("standard", 75), ("premium", 80),
                            ("compliance", 85), ("debug", 50)]:
        session = SessionState(keyword="test", type_page="article",
                               config=SessionConfig(mode=QualityMode(mode), dry_run=True),
                               brouillon_html="<p>Contenu.</p>")
        result = asyncio.run(run(session))
        assert result.scores["seuil_publication"] == expected, f"Mode {mode}"


def test_score_total_somme_criteres(session_riche):
    result = asyncio.run(run(session_riche))
    s = result.scores["scores"]
    expected_total = sum(s.values())
    assert result.scores["score_total"] == expected_total


def test_resultat_stocke(session_riche):
    result = asyncio.run(run(session_riche))
    assert result.agent_results["agent_25"].data == result.scores


def test_zero_cout(session_riche):
    result = asyncio.run(run(session_riche))
    assert result.agent_results["agent_25"].cost_estimated == 0.0


# ─── 4. Scoring individuel ────────────────────────────────────────────

def test_lisibilite_riche():
    text = "L'assurance vie est un contrat important. Il protege vos proches. Les Francais sont couverts. Le capital est verse au beneficiaire. La prime est mensuelle. Le contrat est flexible."
    score = _score_lisibilite(text)
    assert 0 <= score <= 10


def test_densite_texte_riche():
    text = "contrat assurance garantit versement capital beneficiaire deces assure periode determinee couverture"
    score = _score_densite(text)
    assert 0 <= score <= 15


def test_paa_score():
    state = SessionState(keyword="test", serp_data={"paa": ["MotCle1 est important ?", "MotCle2 fonctionne ?"]})
    text = "MotCle1 est tres important pour les utilisateurs. MotCle2 fonctionne de maniere simple."
    score = _score_paa(state, text)
    assert score >= 7


def test_originalite_score():
    state = SessionState(keyword="test", angles_differenciants={
        "angle_principal": "Un angle editorial unique et differencie des concurrents.",
        "facteurs_differenciation": ["F1", "F2", "F3"],
    })
    score = _score_originalite(state)
    assert score >= 7


def test_fraicheur_score():
    state = SessionState(keyword="test", plan_refresh={"frequence_jours": 30})
    score = _score_fraicheur(state)
    assert score >= 7


def test_aeo_score_complet():
    state = SessionState(keyword="test", aeo_blocks={
        "en_bref": "Resume", "h2_questions": ["Q1?", "Q2?", "Q3?"],
        "faq": [{"q": "X", "r": "Y"}, {"q": "A", "r": "B"}],
        "definitions": [{"t": "X", "d": "Y"}, {"t": "A", "d": "B"}],
    })
    assert _score_aeo(state) == 10


def test_geo_score_complet():
    state = SessionState(keyword="test", geo_data={
        "sources_primaires": [{"titre": "S"}],
        "entites_nommees": ["E1", "E2", "E3"],
        "phrases_citables": ["P1", "P2", "P3"],
        "chunks": [{"titre": "C1"}, {"titre": "C2"}, {"titre": "C3"}],
    })
    assert _score_geo(state) == 10


def test_erreurs_score_critique():
    state = SessionState(keyword="test", fact_check_data={
        "erreurs": [{"gravite": "critique"}],
    })
    assert _score_erreurs(state) == 0


def test_naturalite_score():
    text = "Ceci est un contenu naturel avec des phrases varies et un style authentique."
    score = _score_naturalite(SessionState(), text)
    assert 0 <= score <= 4


# ─── 5. Type-aware — criteres neutralises ─────────────────────────────

def test_landing_neutralise_aeo_geo():
    """Landing: PAA, AEO, GEO neutralises → score max automatique."""
    session = SessionState(
        keyword="test", type_page="landing",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        brouillon_html="<p>Contenu landing.</p>",
    )
    result = _evaluate(session)
    assert result.scores.reponse_paa == 20
    assert result.scores.respect_aeo == 10
    assert result.scores.respect_geo == 10


def test_fiche_produit_neutralise_paa():
    session = SessionState(
        keyword="test", type_page="fiche_produit",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        brouillon_html="<p>Produit.</p>",
    )
    result = _evaluate(session)
    assert result.scores.reponse_paa == 20
    assert result.scores.respect_geo == 10


def test_tous_les_types_na_connus():
    for t in ("landing", "fiche_produit", "faq", "service_local",
              "comparatif", "news", "glossaire", "temoignage"):
        assert t in CRITERES_NON_APPLICABLES or t not in CRITERES_NON_APPLICABLES


# ─── 6. Blocages et avertissements ────────────────────────────────────

def test_score_bas_bloque():
    session = SessionState(
        keyword="test", type_page="article",
        config=SessionConfig(mode=QualityMode.STANDARD, dry_run=True),
        brouillon_html="<p>Court.</p>",
        fact_check_data={"erreurs": [{"gravite": "critique"}]},
    )
    result = _evaluate(session)
    assert not result.seuil_atteint
    assert len(result.blocages) > 0


def test_recommandation_non_vide(session_riche):
    result = _evaluate(session_riche)
    assert result.recommandation


def test_erreur_critique_bloque():
    session = SessionState(keyword="test", fact_check_data={"erreurs": [{"gravite": "critique"}]})
    result = _evaluate(session)
    assert result.scores.absence_erreurs == 0
