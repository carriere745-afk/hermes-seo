"""Tests unitaires pour Agent 03 — Analyse SERP."""

import asyncio

import pytest

from hermes.agents.agent_03_analyse_serp import (
    _extract_domain,
    _parse_raw_results,
    _build_user_message,
    _extract_json,
    _enrich_with_llm,
    _mock_serp,
    run,
)
from hermes.models.agent_data import SerpData, SerpResult
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def session_valide():
    return SessionState(
        keyword="assurance vie temporaire",
        site_url="https://www.monassureur.fr",
        objectif="Article pilier",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={
            "nom": "MonAssureur", "secteur": "finance",
            "positionnement": "Courtier digital",
        },
        fiche_persona={
            "nom_persona": "Paul 45 ans", "maturite": "intermediaire",
        },
        agent_results={
            "agent_01": AgentResult(agent_id="agent_01", status=AgentStatus.COMPLETED),
            "agent_02": AgentResult(agent_id="agent_02", status=AgentStatus.COMPLETED),
        },
    )


@pytest.fixture
def hasdata_response():
    """Reponse brute simulee au format HasData."""
    return {
        "organic_results": [
            {
                "position": 1,
                "title": "Guide complet assurance vie",
                "link": "https://www.assurland.com/guide",
                "snippet": "Tout savoir sur l'assurance vie temporaire...",
            },
            {
                "position": 2,
                "title": "Comparatif 2026",
                "link": "https://www.meilleurtaux.com/comparatif",
                "snippet": "Comparez les meilleures offres...",
            },
        ],
        "related_questions": [
            {"question": "Qu'est-ce que l'assurance vie temporaire ?"},
            {"question": "Comment ça fonctionne ?"},
        ],
        "featured_snippet": {
            "title": "Definition",
            "content": "L'assurance vie temporaire est un contrat...",
        },
    }


@pytest.fixture
def serpstack_response():
    """Reponse brute simulee au format Serpstack."""
    return {
        "organic_results": [
            {
                "position": 1,
                "title": "Guide complet",
                "url": "https://www.exemple.fr/guide",
                "snippet": "Un guide complet...",
                "domain": "exemple.fr",
            },
        ],
        "related_questions": [
            "Question 1 ?",
            "Question 2 ?",
        ],
    }


# ─── 1. Entrée valide ─────────────────────────────────────────────────

def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.serp_data is not None
    assert len(result.serp_data["top10"]) == 10
    assert result.serp_data["top10"][0]["position"] == 1
    agent_result = result.agent_results["agent_03"]
    assert agent_result.status == AgentStatus.COMPLETED


def test_run_serp_data_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    serp = SerpData.model_validate(result.serp_data)
    assert len(serp.top10) == 10
    assert len(serp.paa) > 0
    assert len(serp.concurrents_directs) > 0


# ─── 2. Entrée invalide ────────────────────────────────────────────────

def test_run_keyword_vide():
    session = SessionState(
        keyword="",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    result = asyncio.run(run(session))
    # L'agent fonctionne même avec keyword vide (mock tolerant)
    assert result.serp_data is not None
    assert result.agent_results["agent_03"].status == AgentStatus.COMPLETED


def test_run_secteur_inconnu():
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="inconnu"),
    )
    result = asyncio.run(run(session))
    assert len(result.serp_data["top10"]) == 10


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_serp_data_tous_les_champs(session_valide):
    result = asyncio.run(run(session_valide))
    data = result.serp_data
    assert "top10" in data
    assert "paa" in data
    assert "featured_snippets" in data
    assert "ai_overviews" in data
    assert "concurrents_directs" in data
    assert "mots_cles_associes" in data
    assert isinstance(data["top10"], list)
    assert isinstance(data["paa"], list)


def test_top10_elements_structure(session_valide):
    result = asyncio.run(run(session_valide))
    first = result.serp_data["top10"][0]
    assert "position" in first
    assert "title" in first
    assert "url" in first
    assert "snippet" in first
    assert "domain" in first


def test_resultat_stocke_dans_session(session_valide):
    result = asyncio.run(run(session_valide))
    agent_result = result.agent_results.get("agent_03")
    assert agent_result is not None
    assert agent_result.data == result.serp_data


def test_last_completed_agent_id(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.last_completed_agent_id == "agent_03"


# ─── 4. Erreur contrôlée ───────────────────────────────────────────────

def test_relance_ecrase_ancien_resultat(session_valide):
    result1 = asyncio.run(run(session_valide))
    first_paa = result1.serp_data["paa"][0]
    result2 = asyncio.run(run(result1))
    assert result2.agent_results["agent_03"].status == AgentStatus.COMPLETED
    assert result2.serp_data["paa"][0] == first_paa  # dry-run deterministe


# ─── 5. Parsing reponse API ────────────────────────────────────────────

def test_parse_hasdata_format(hasdata_response):
    parsed = _parse_raw_results(hasdata_response)
    assert len(parsed["organic_results"]) == 2
    assert parsed["organic_results"][0]["domain"] == "assurland.com"
    assert parsed["organic_results"][0]["url"] == "https://www.assurland.com/guide"
    assert len(parsed["related_questions"]) == 2
    assert parsed["featured_snippet"]["title"] == "Definition"


def test_parse_serpstack_format(serpstack_response):
    parsed = _parse_raw_results(serpstack_response)
    assert len(parsed["organic_results"]) == 1
    assert parsed["organic_results"][0]["domain"] == "exemple.fr"
    assert len(parsed["related_questions"]) == 2


def test_parse_empty_response():
    parsed = _parse_raw_results({})
    assert parsed["organic_results"] == []
    assert parsed["related_questions"] == []
    assert parsed["featured_snippet"] == {}


# ─── 6. Extraction de domaine ──────────────────────────────────────────

def test_extract_domain_simple():
    assert _extract_domain("https://www.exemple.fr/article") == "exemple.fr"


def test_extract_domain_sans_www():
    assert _extract_domain("https://exemple.fr/page") == "exemple.fr"


def test_extract_domain_avec_path():
    assert _extract_domain("https://blog.exemple.fr/2024/01/test") == "blog.exemple.fr"


def test_extract_domain_invalide():
    # urlparse sur une chaine sans schema peut retourner vide
    result = _extract_domain("pas-une-url")
    assert result in ("pas-une-url", "")  # depend de l'implementation d'urlparse


# ─── 7. LLM enrichment ─────────────────────────────────────────────────

def test_enrich_with_llm_full():
    parsed = {
        "organic_results": [
            {"position": 1, "domain": "site1.fr", "title": "T1", "url": "u1", "snippet": "s1"},
            {"position": 2, "domain": "site2.fr", "title": "T2", "url": "u2", "snippet": "s2"},
        ],
        "related_questions": [],
        "featured_snippet": {},
        "ai_overview": {},
    }
    llm_text = '{"concurrents_directs": ["site1.fr", "site2.fr"], "mots_cles_associes": ["kw1", "kw2"], "search_volume": 500, "keyword_difficulty": 30}'
    data = _enrich_with_llm(parsed, "test", llm_text)
    assert data["concurrents_directs"] == ["site1.fr", "site2.fr"]
    assert data["search_volume"] == 500


def test_enrich_with_llm_fallback_domaines():
    parsed = {
        "organic_results": [
            {"position": 1, "domain": "fallback.fr", "title": "T", "url": "u", "snippet": "s"},
        ],
        "related_questions": [], "featured_snippet": {}, "ai_overview": {},
    }
    llm_text = "texte invalide"
    data = _enrich_with_llm(parsed, "test", llm_text)
    assert "fallback.fr" in data["concurrents_directs"]


# ─── 8. Build user message ─────────────────────────────────────────────

def test_build_user_message(hasdata_response):
    parsed = _parse_raw_results(hasdata_response)
    msg = _build_user_message(parsed, "assurance vie")
    assert "assurance vie" in msg
    assert "assurland.com" in msg


# ─── 9. Mock dry-run ───────────────────────────────────────────────────

def test_mock_serp_finance():
    serp = _mock_serp("assurance vie", "finance")
    assert len(serp.top10) == 10
    assert serp.top10[0].position == 1
    assert "service-public.fr" in str(serp.concurrents_directs) or "assurland" in str(serp.concurrents_directs)
    assert len(serp.paa) >= 5
    assert len(serp.mots_cles_associes) >= 5


def test_mock_serp_sante():
    serp = _mock_serp("traitement migraine", "sante")
    assert "ameli.fr" in serp.concurrents_directs or "vidal.fr" in serp.concurrents_directs


def test_mock_serp_saas():
    serp = _mock_serp("logiciel crm", "saas")
    assert len(serp.top10) == 10
    assert len(serp.paa) >= 5


def test_mock_serp_values_present():
    serp = _mock_serp("test", "saas")
    assert serp.search_volume is not None
    assert serp.keyword_difficulty is not None
    assert 0 <= serp.keyword_difficulty <= 100


# ─── 10. JSON extraction ───────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_invalide():
    assert _extract_json("pas du json") == {}
