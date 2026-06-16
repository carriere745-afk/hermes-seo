"""Tests unitaires pour Agent 12 — GEO."""

import asyncio

import pytest

from hermes.agents.agent_12_geo import (
    GEO_PROFILES, _extract_json, _build_user_message, _mock_geo, run,
)
from hermes.models.agent_data import GeoData
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_pilier():
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        type_page="pilier",
        fiche_entreprise={"nom": "MonAssureur", "secteur": "finance"},
        brouillon_html=(
            "<h1>Guide Complet Assurance Vie Temporaire</h1>"
            "<p>L'assurance vie temporaire est un contrat essentiel pour proteger "
            "votre famille. Selon les chiffres de la Federation Francaise de l'Assurance, "
            "plus de 10 millions de Francais sont couverts.</p>"
        ),
        serp_data={"concurrents_directs": ["assurland.com", "meilleurtaux.com"]},
        angles_differenciants={"angle_principal": "Guide exhaustif avec donnees verificables"},
        agent_results={
            "agent_09": AgentResult(agent_id="agent_09", status=AgentStatus.COMPLETED),
        },
    )


# ─── 1. Entree valide ─────────────────────────────────────────────────

def test_run_pilier(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert result.geo_data is not None
    assert len(result.geo_data["sources_primaires"]) >= 3
    assert len(result.geo_data["entites_nommees"]) >= 5
    assert len(result.geo_data["phrases_citables"]) >= 5
    assert len(result.geo_data["chunks"]) >= 4
    assert result.agent_results["agent_12"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_pilier):
    result = asyncio.run(run(session_pilier))
    GeoData.model_validate(result.geo_data)


# ─── 2. Entree invalide ────────────────────────────────────────────────

def test_run_sans_brouillon():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.geo_data is not None


def test_run_keyword_vide():
    session = SessionState(keyword="", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert result.agent_results["agent_12"].status == AgentStatus.COMPLETED


# ─── 3. Sortie conforme ────────────────────────────────────────────────

def test_geo_tous_les_champs(session_pilier):
    result = asyncio.run(run(session_pilier))
    for field in ("sources_primaires", "entites_nommees", "phrases_citables", "chunks"):
        assert field in result.geo_data, f"Champ manquant: {field}"


def test_sources_format_valide(session_pilier):
    for src in asyncio.run(run(session_pilier)).geo_data["sources_primaires"]:
        assert "titre" in src
        assert "url" in src
        assert "type" in src


def test_entites_sont_des_strings(session_pilier):
    entites = asyncio.run(run(session_pilier)).geo_data["entites_nommees"]
    assert all(isinstance(e, str) for e in entites)


def test_chunks_format_valide(session_pilier):
    for chunk in asyncio.run(run(session_pilier)).geo_data["chunks"]:
        assert "titre" in chunk
        assert "contenu" in chunk


def test_phrases_citables_sont_des_phrases(session_pilier):
    citations = asyncio.run(run(session_pilier)).geo_data["phrases_citables"]
    assert all(len(c) > 20 for c in citations)


def test_resultat_stocke(session_pilier):
    result = asyncio.run(run(session_pilier))
    assert result.agent_results["agent_12"].data == result.geo_data


# ─── 4. Type-aware — chaque type de page ───────────────────────────────

@pytest.mark.parametrize("type_page,min_sources,min_chunks", [
    ("pilier", 3, 4),
    ("article", 1, 3),
    ("fiche_produit", 1, 2),
    ("landing", 0, 1),
    ("comparatif", 2, 3),
    ("service_local", 0, 2),
    ("news", 2, 2),
    ("faq", 1, 5),
    ("glossaire", 1, 2),
    ("temoignage", 0, 2),
])
def test_mock_respecte_profil_minimal(type_page, min_sources, min_chunks):
    session = SessionState(keyword="test", type_page=type_page,
                           fiche_entreprise={"nom": "TestCorp"},
                           config=SessionConfig(dry_run=True))
    geo = _mock_geo(session)
    assert len(geo.sources_primaires) >= min_sources, \
        f"{type_page}: {len(geo.sources_primaires)} < {min_sources} sources"
    assert len(geo.chunks) >= min_chunks, \
        f"{type_page}: {len(geo.chunks)} < {min_chunks} chunks"


# ─── 5. Profils GEO ────────────────────────────────────────────────────

def test_tous_les_types_ont_profil():
    types = ["pilier", "article", "fiche_produit", "faq", "service_local",
             "comparatif", "landing", "news", "glossaire", "temoignage"]
    for t in types:
        assert t in GEO_PROFILES, f"Profil GEO manquant pour {t}"


def test_profils_ont_tous_les_champs():
    for t, p in GEO_PROFILES.items():
        for field in ("min_sources", "min_entites", "min_citations", "min_chunks"):
            assert field in p, f"Champ {field} manquant dans le profil GEO {t}"


# ─── 6. Build user message ─────────────────────────────────────────────

def test_build_message_contient_profil(session_pilier):
    msg = _build_user_message(session_pilier)
    assert "sources" in msg.lower()
    assert "pilier" in msg


# ─── 7. JSON extraction ────────────────────────────────────────────────

def test_extract_json_valide():
    assert _extract_json('{"entites_nommees": ["a"]}')["entites_nommees"] == ["a"]
