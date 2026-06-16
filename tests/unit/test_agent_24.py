"""Tests unitaires pour Agent 24 — Mise a jour."""

import asyncio, pytest, re
from hermes.agents.agent_24_mise_a_jour import run
from hermes.models.agent_data import RefreshPlan
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


def _session(type_page="article", secteur="saas", **kw):
    return SessionState(
        keyword="test", type_page=type_page,
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur=secteur),
        fiche_entreprise={"nom": "TestCorp", "secteur": secteur},
        geo_data={"sources_primaires": [{"url": "https://service-public.fr"}]},
        fact_check_data={"score_fiabilite": 9},
        **kw,
    )


# ─── 1. Entree valide ────────────────────────────────────────────────

def test_run_article():
    result = asyncio.run(run(_session("article", "saas")))
    assert result.plan_refresh is not None
    assert result.plan_refresh["frequence_jours"] == 180
    assert re.match(r"\d{4}-\d{2}-\d{2}", result.plan_refresh["date_prochaine_revision"])
    assert result.agent_results["agent_24"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide():
    RefreshPlan.model_validate(asyncio.run(run(_session())).plan_refresh)


# ─── 2. Frequences par type ──────────────────────────────────────────

@pytest.mark.parametrize("type_page,expected_days", [
    ("news", 7), ("comparatif", 60), ("pilier", 90),
    ("fiche_produit", 90), ("landing", 90), ("service_local", 90),
    ("faq", 120), ("article", 180), ("glossaire", 365), ("temoignage", 180),
])
def test_frequence_par_type(type_page, expected_days):
    result = asyncio.run(run(_session(type_page, "saas")))
    assert result.plan_refresh["frequence_jours"] == expected_days


# ─── 3. Acceleration sectorielle ──────────────────────────────────────

def test_cybersecurite_accelere():
    result = asyncio.run(run(_session("article", "cybersecurite")))
    assert result.plan_refresh["frequence_jours"] == 30


def test_finance_accelere():
    result = asyncio.run(run(_session("article", "finance")))
    assert result.plan_refresh["frequence_jours"] == 60


def test_pilier_finance_prend_le_min():
    result = asyncio.run(run(_session("pilier", "finance")))
    assert result.plan_refresh["frequence_jours"] == 60  # min(90, 60)


# ─── 4. Sortie conforme ────────────────────────────────────────────────

def test_plan_tous_les_champs():
    result = asyncio.run(run(_session()))
    for field in ("date_prochaine_revision", "frequence_jours", "criteres_obsolescence", "sources_a_surveiller"):
        assert field in result.plan_refresh


def test_criteres_non_vides():
    result = asyncio.run(run(_session()))
    assert len(result.plan_refresh["criteres_obsolescence"]) >= 2


def test_sources_presentes():
    result = asyncio.run(run(_session()))
    assert len(result.plan_refresh["sources_a_surveiller"]) >= 1


def test_resultat_stocke():
    result = asyncio.run(run(_session()))
    assert result.agent_results["agent_24"].data == result.plan_refresh


def test_zero_cout():
    result = asyncio.run(run(_session()))
    assert result.agent_results["agent_24"].cost_estimated == 0.0
