"""Tests unitaires Pipeline 5 — Strategie Editoriale.

Teste chaque agent individuellement puis le pipeline complet.
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

from hermes.models.strategie import (
    StrategieState, Recommandation, KillListEntry,
    ExecutiveSummary, DecisionTrace, Sujet, GapConcurrentiel,
    ForecastEntry, HermesEvent, PredictionEntry,
)
from hermes.agents.strategie import (
    STRATEGIE_REGISTRY, STRATEGIE_ORDER,
)
from hermes.core.strategie_db import init_db, log_event, save_prediction, get_db_stats


# ─── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def base_state():
    return StrategieState(
        site_url="https://example.com",
        domain="example.com",
        mode="standard",
        profile="blog",
        keywords_monitored=["guide seo", "outils seo", "formation seo", "agence seo"],
        competitors=["concurrent1.com", "concurrent2.com"],
        valeur_lead=100.0,
        taux_conversion=0.02,
    )


@pytest.fixture
def state_with_sujets(base_state):
    state = base_state
    state.sujets = [
        Sujet(nom="Guide SEO", keywords=["guide seo"], volume_total=1500, silo="seo",
              intention="informative", couvert=False, topical_authority=60),
        Sujet(nom="Outils SEO", keywords=["outils seo"], volume_total=800, silo="seo",
              intention="comparative", couvert=True, page_existante="/outils-seo",
              topical_authority=70, position_moyenne=5.0),
        Sujet(nom="Formation SEO", keywords=["formation seo"], volume_total=2000, silo="formation",
              intention="transactionnelle", couvert=False, topical_authority=40),
    ]
    state.topical_map = [
        {"silo": "seo", "sujets_couverts": 1, "sujets_manquants": 1, "volume_total": 2300,
         "sujets": [{"nom": "Guide SEO", "couvert": False, "volume": 1500},
                     {"nom": "Outils SEO", "couvert": True, "volume": 800}]},
        {"silo": "formation", "sujets_couverts": 0, "sujets_manquants": 1, "volume_total": 2000,
         "sujets": [{"nom": "Formation SEO", "couvert": False, "volume": 2000}]},
    ]
    state.startup_ok = True
    state.pipelines_disponibles = {"p2": False, "p3": False, "p4": False}
    return state


# ─── Tests ST00 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st00_startup(base_state):
    state = base_state
    state.session_id = ""  # Force regeneration
    result = await STRATEGIE_REGISTRY["st00"](state)
    assert result.startup_ok is True
    assert result.session_id.startswith("strat-example.com")
    assert result.status == "running"
    assert "st00" in result.current_agent


# ─── Tests ST01 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st01_topical_map(base_state):
    state = base_state
    result = await STRATEGIE_REGISTRY["st01"](state)
    assert len(result.sujets) > 0
    assert len(result.topical_map) > 0
    assert result.current_agent == "st01"


# ─── Tests ST01b ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st01b_topical_authority(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st01b"](state)
    assert len(result.topical_authority_scores) >= 1
    assert result.topical_authority_scores.get("seo", 0) >= 0
    assert result.sujets[0].topical_authority >= 0


# ─── Tests ST02 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st02_cannibalisation(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st02"](state)
    assert isinstance(result.cannibalisations, list)
    assert result.current_agent == "st02"


# ─── Tests ST03 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st03_opportunites(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st03"](state)
    assert len(result.opportunites) > 0
    assert "opportunite_score" in result.opportunites[0]


# ─── Tests ST04 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st04_gap_concurrentiel(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st04"](state)
    assert isinstance(result.gaps_concurrentiels, list)
    assert result.current_agent == "st04"


# ─── Tests ST04b ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st04b_feasibility(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st04b"](state)
    assert len(result.feasibility_scores) >= 1
    score = result.feasibility_scores.get("Guide SEO", 0)
    assert 0 <= score <= 100


# ─── Tests ST04c ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st04c_geo_opportunity(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st04c"](state)
    assert isinstance(result.geo_opportunities, list)


@pytest.mark.asyncio
async def test_st04c_skip_fast(state_with_sujets):
    state = state_with_sujets
    state.mode = "fast"
    result = await STRATEGIE_REGISTRY["st04c"](state)
    assert result.geo_opportunities == []


# ─── Tests ST05 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st05_business_score(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st05"](state)
    assert len(result.business_scores) >= 1
    score = result.business_scores.get("Formation SEO", 0)
    assert 0 <= score <= 100


# ─── Tests ST05b ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st05b_seo_economics(state_with_sujets):
    state = state_with_sujets
    state.business_scores = {"Guide SEO": 60.0, "Outils SEO": 75.0, "Formation SEO": 85.0}
    result = await STRATEGIE_REGISTRY["st05b"](state)
    assert len(result.seo_economics) >= 1
    eco = result.seo_economics[0]
    assert "roi_12mois" in eco
    assert "effort_estime" in eco


@pytest.mark.asyncio
async def test_st05b_skip_fast(state_with_sujets):
    state = state_with_sujets
    state.mode = "fast"
    result = await STRATEGIE_REGISTRY["st05b"](state)
    assert result.seo_economics == []


# ─── Tests ST06 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st06_roadmap(state_with_sujets):
    state = state_with_sujets
    state.feasibility_scores = {"Guide SEO": 65, "Outils SEO": 80, "Formation SEO": 45}
    state.business_scores = {"Guide SEO": 60.0, "Outils SEO": 75.0, "Formation SEO": 85.0}
    state.seo_economics = [
        {"sujet": "Guide SEO", "effort_estime": "4h", "cout_creation": 200, "trafic_mensuel_estime": 100,
         "leads_mensuels_estimes": 2, "roi_12mois": 500, "delai_resultats": "3-6 mois"},
    ]
    state.opportunites = [
        {"sujet": "Guide SEO", "keywords": ["guide seo"], "volume_total": 1500,
         "opportunite_score": 70, "type_page_recommande": "article",
         "intention": "informative", "silo": "seo", "position_moyenne": 100.0,
         "concurrents_top5": ["concurrent1.com"]},
    ]
    result = await STRATEGIE_REGISTRY["st06"](state)
    # Devrait avoir au moins les recos d'opportunites et cannibalisations si existantes
    assert isinstance(result.recommandations, list)
    for rec in result.recommandations:
        assert 0 <= rec.confidence_score <= 100
        assert rec.trace is not None


# ─── Tests ST06b ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st06b_forecast(state_with_sujets):
    state = state_with_sujets
    state.recommandations = [
        Recommandation(sujet="Test", action="creer_pilier", priorite="P1",
                       volume_recherche=1000, trafic_estime=100, leads_estimes=2,
                       roi_12mois=500, cout_estime=200, effort_estime="4h",
                       confidence_score=75),
    ]
    result = await STRATEGIE_REGISTRY["st06b"](state)
    assert len(result.forecast) == 12


@pytest.mark.asyncio
async def test_st06b_skip_fast(state_with_sujets):
    state = state_with_sujets
    state.mode = "fast"
    result = await STRATEGIE_REGISTRY["st06b"](state)
    assert result.forecast == []


# ─── Tests ST06c ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st06c_portfolio(state_with_sujets):
    state = state_with_sujets
    state.recommandations = [
        Recommandation(sujet="Creer pilier", action="creer_pilier", priorite="P1"),
        Recommandation(sujet="Fusion pages", action="fusionner", priorite="P1"),
    ]
    result = await STRATEGIE_REGISTRY["st06c"](state)
    assert len(result.portfolio_allocation) == 5
    assert sum(result.portfolio_allocation.values()) == pytest.approx(100.0, abs=0.2)


@pytest.mark.asyncio
async def test_st06c_skip_fast(state_with_sujets):
    state = state_with_sujets
    state.mode = "fast"
    result = await STRATEGIE_REGISTRY["st06c"](state)
    assert result.portfolio_allocation == {}


# ─── Tests ST07 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st07_silos_clusters(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st07"](state)
    assert len(result.silos_analysis) >= 1
    silo = result.silos_analysis[0]
    assert "issues" in silo
    assert "recommandations" in silo


# ─── Tests ST08 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st08_fusion_separation(state_with_sujets):
    state = state_with_sujets
    result = await STRATEGIE_REGISTRY["st08"](state)
    assert isinstance(result.fusion_separation, list)


# ─── Tests ST09 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st09_revue_humaine_ymyl(state_with_sujets):
    state = state_with_sujets
    state.recommandations = [
        Recommandation(sujet="Traitement maladie", keywords=["traitement", "maladie"], priorite="P1"),
        Recommandation(sujet="Guide SEO", keywords=["guide seo"], priorite="P1"),
    ]
    result = await STRATEGIE_REGISTRY["st09"](state)
    assert len(result.revue_humaine_flags) >= 1
    assert result.revue_humaine_flags[0]["sujet"] == "Traitement maladie"
    assert result.revue_humaine_flags[0]["ymyl"] is True


@pytest.mark.asyncio
async def test_st09_skip_fast(state_with_sujets):
    state = state_with_sujets
    state.mode = "fast"
    result = await STRATEGIE_REGISTRY["st09"](state)
    assert result.revue_humaine_flags == []


# ─── Tests ST10 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st10_priorisation(state_with_sujets):
    state = state_with_sujets
    state.feasibility_scores = {"Guide SEO": 65, "Test": 80}
    state.business_scores = {"Guide SEO": 60.0, "Test": 75.0}
    state.recommandations = [
        Recommandation(sujet="Test", keywords=["test"], action="creer_pilier",
                       priorite="P2", volume_recherche=5000, effort_estime="2h"),
    ]
    result = await STRATEGIE_REGISTRY["st10"](state)
    assert result.recommandations[0].priorite in ("P0", "P1", "P2", "P3")


# ─── Tests ST10b ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st10b_kill_list(state_with_sujets):
    state = state_with_sujets
    state.recommandations = [
        Recommandation(sujet="Sujet mort", priorite="KILL", keywords=["mort"],
                       justification="Hors scope"),
    ]
    result = await STRATEGIE_REGISTRY["st10b"](state)
    assert len(result.kill_list) >= 1
    assert result.kill_list[0].categorie == "faible_potentiel"


# ─── Tests ST11 ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_st11_export(state_with_sujets):
    state = state_with_sujets
    state.feasibility_scores = {"Guide SEO": 65}
    state.business_scores = {"Guide SEO": 60.0}
    state.topical_authority_scores = {"seo": 60}
    state.opportunites = [
        {"sujet": "Guide SEO", "volume_total": 1500, "opportunite_score": 70,
         "type_page_recommande": "article", "potentiel": "+75 visites/mois"},
    ]
    state.recommandations = [
        Recommandation(sujet="Guide SEO", action="creer_article", priorite="P1",
                       volume_recherche=1500, trafic_estime=75, leads_estimes=1,
                       roi_12mois=500, cout_estime=200, effort_estime="4h",
                       confidence_score=75, pipeline_cible="P1"),
    ]
    result = await STRATEGIE_REGISTRY["st11"](state)
    assert result.executive_summary is not None
    assert result.executive_summary.sante_strategique >= 0
    assert len(result.executive_summary.top_opportunites) > 0
    assert len(result.rapport_html) > 0
    assert len(result.rapport_json) > 0
    assert result.status == "completed"


# ─── Tests DB ─────────────────────────────────────────────────────────────

def test_init_db():
    init_db()
    stats = get_db_stats()
    assert "hermes_events" in stats


def test_log_event():
    event_id = log_event(
        session_id="test-session", agent_id="st00",
        pipeline_id="strategie", model="none",
        tokens_used=100, cost=0.01, duration_ms=500,
        success=True, predictions={"traffic": 100},
        confidence=0.8, trace={"decision": "P1"},
    )
    assert len(event_id) == 12


def test_save_prediction():
    pred_id = save_prediction(
        session_id="test-session", agent_id="st06",
        action_type="creer_pilier", keyword="test",
        predicted_traffic=500, predicted_leads=5,
        predicted_roi=1000.0, confidence=80.0,
    )
    assert len(pred_id) == 12


# ─── Tests Modeles ───────────────────────────────────────────────────────

def test_recommandation_model():
    rec = Recommandation(
        sujet="Test", action="creer_pilier", priorite="P1",
        volume_recherche=1000, confidence_score=75,
        confidence_justification="Confiance moyenne - donnees partielles, incertitude moderee",
        trace=DecisionTrace(
            inputs={"vol": 1000}, rules_applied=["rule1"],
            calcul="1+1=2", decision="P1",
        ),
    )
    assert rec.id
    assert "Confiance" in rec.confidence_justification


def test_executive_summary_model():
    es = ExecutiveSummary(
        sante_strategique=75,
        top_opportunites=[{"sujet": "Test", "volume": 1000}],
        top_menaces=[{"type": "Cannibalisation", "impact": "Dilution"}],
        roi_12mois_bas=5000, roi_12mois_haut=8000,
        budget_mensuel_recommande=500,
    )
    assert es.sante_strategique == 75
    assert len(es.top_opportunites) == 1


def test_strategie_state_serialization(base_state):
    js = base_state.model_dump_json()
    assert "example.com" in js
    restored = StrategieState.model_validate_json(js)
    assert restored.domain == "example.com"


def test_kill_list_entry():
    entry = KillListEntry(
        sujet="Test", raison="Faible potentiel",
        categorie="faible_potentiel", severite="critical",
        justification="Pas rentable",
        trace=DecisionTrace(inputs={"score": 10}, rules_applied=[],
                            calcul="score<20", decision="KILL"),
    )
    assert entry.severite == "critical"
    assert entry.trace is not None


# ─── Test Pipeline Complet ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_pipeline_standard(base_state):
    """Test du pipeline complet en mode standard."""
    state = base_state
    state.mode = "standard"

    for agent_id in STRATEGIE_ORDER:
        if agent_id in STRATEGIE_REGISTRY:
            state = await STRATEGIE_REGISTRY[agent_id](state)

    assert state.status == "completed"
    assert len(state.sujets) > 0
    assert state.executive_summary is not None
    assert len(state.rapport_html) > 0


@pytest.mark.asyncio
async def test_full_pipeline_fast(base_state):
    """Test du pipeline complet en mode fast."""
    state = base_state
    state.mode = "fast"

    for agent_id in STRATEGIE_ORDER:
        if agent_id in STRATEGIE_REGISTRY:
            state = await STRATEGIE_REGISTRY[agent_id](state)

    assert state.status == "completed"
    assert state.executive_summary is not None


@pytest.mark.asyncio
async def test_full_pipeline_no_keywords(base_state):
    """Test sans mots-cles — doit fonctionner avec les defauts."""
    state = base_state
    state.keywords_monitored = []
    state.mode = "standard"

    for agent_id in STRATEGIE_ORDER:
        if agent_id in STRATEGIE_REGISTRY:
            state = await STRATEGIE_REGISTRY[agent_id](state)

    assert state.status == "completed"
