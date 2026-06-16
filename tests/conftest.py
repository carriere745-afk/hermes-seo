"""Fixtures partagées pour tous les tests Hermes SEO."""

import json
from pathlib import Path

import pytest

from hermes.models.common import QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def sample_session() -> SessionState:
    """Session valide minimale pour les tests."""
    return SessionState(
        keyword="test mot cle",
        site_url="https://exemple.fr",
        objectif="Test unitaire",
        config=SessionConfig(
            mode=QualityMode.DEBUG,
            dry_run=True,
            secteur="saas",
        ),
    )


@pytest.fixture
def complete_session() -> SessionState:
    """Session avec tous les champs remplis."""
    return SessionState(
        keyword="assurance vie temporaire",
        site_url="https://monassureur.fr",
        objectif="Article pilier assurance vie",
        contraintes=["Ne pas mentionner de prix", "Inclure mentions légales"],
        config=SessionConfig(
            mode=QualityMode.PREMIUM,
            dry_run=True,
            secteur="finance",
            token_budget=500000,
            cost_budget=3.0,
        ),
        fiche_entreprise={
            "nom": "MonAssureur",
            "secteur": "finance",
            "positionnement": "Courtier en ligne",
            "offres": ["Assurance vie temporaire", "Assurance vie permanente"],
            "ton_marque": "Professionnel rassurant",
            "preuves": ["Agréé AMF", "100 000 clients"],
            "contraintes_legales": ["Mentions légales assurance", "Avertissement fiscal"],
            "mots_cles_interdits": ["gratuit"],
            "elements_differenciants": ["Comparateur intégré", "Souscription 100% en ligne"],
        },
        fiche_persona={
            "nom_persona": "Paul 45 ans",
            "maturite": "intermediaire",
            "vocabulaire_recommande": ["prime", "capital", "bénéficiaire"],
            "canal_acquisition": "search",
            "objectif_lecture": "Comprendre les options avant achat",
            "freins": ["Peur de s'engager", "Termes trop techniques"],
            "questions_typiques": ["Quelle différence entre temporaire et permanente ?"],
        },
        serp_data={
            "top10": [
                {"position": 1, "title": "Guide assurance vie", "url": "https://exemple.fr",
                 "snippet": "Tout savoir sur l'assurance vie", "domain": "exemple.fr"},
            ],
            "paa": ["Qu'est-ce que l'assurance vie temporaire ?"],
            "concurrents_directs": ["assurland.com", "meilleurtaux.com"],
        },
        intention="informative",
        type_page="pilier",
        template_data={
            "template_id": "pilier_v1",
            "nom": "Article Pilier",
            "structure": [
                {"type": "h1", "titre": "Guide complet", "obligatoire": True, "ordre": 0},
                {"type": "h2", "titre": "Définition", "obligatoire": True, "ordre": 1},
                {"type": "h2", "titre": "Fonctionnement", "obligatoire": True, "ordre": 2},
                {"type": "h2", "titre": "Avantages", "obligatoire": True, "ordre": 3},
                {"type": "h2", "titre": "FAQ", "obligatoire": True, "ordre": 4},
            ],
        },
        brouillon_html="<h1>Guide complet assurance vie temporaire</h1><p>Contenu test</p>",
        seo_data={
            "title_optimise": "Guide Assurance Vie Temporaire 2026",
            "meta_description_optimise": "Tout savoir sur l'assurance vie temporaire",
        },
        aeo_blocks={
            "en_bref": "L'assurance vie temporaire protège vos proches...",
            "faq": [{"q": "Question ?", "r": "Réponse."}],
        },
        geo_data={
            "entites_nommees": ["Assurance vie", "Code des assurances"],
        },
        score_eeat={"score_global": 12, "score_expertise": 3, "score_experience": 3},
        conformite_data={"valide": True, "risque_juridique": "modere"},
        fact_check_data={"score_fiabilite": 9, "erreurs": []},
    )


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_serp_response() -> dict:
    """Réponse SERP mockée."""
    path = Path(__file__).parent / "fixtures" / "serp" / "response_google.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "keyword": "test",
        "organic_results": [
            {"position": i, "title": f"Résultat {i}", "url": f"https://exemple{i}.fr",
             "snippet": f"Extrait {i}"}
            for i in range(1, 10)
        ],
        "related_questions": ["Question 1 ?", "Question 2 ?"],
    }
