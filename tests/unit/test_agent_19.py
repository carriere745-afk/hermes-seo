"""Tests unitaires pour Agent 19 — Test A/B."""

import asyncio
import pytest

from hermes.agents.agent_19_test_ab import (
    _predict_ctr, _extract_json, _mock_variants, run,
)
from hermes.models.agent_data import VariantsAB
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


@pytest.fixture
def session_valide():
    return SessionState(
        keyword="assurance vie temporaire",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        seo_data={
            "title_optimise": "Guide Assurance Vie Temporaire 2026 | MonAssureur",
            "meta_description_optimise": "Decouvrez tout sur l'assurance vie temporaire. Definition, prix et conseils.",
        },
        agent_results={
            "agent_10": AgentResult(agent_id="agent_10", status=AgentStatus.COMPLETED),
        },
    )


def test_run_avec_session_valide(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.variants_ab is not None
    assert len(result.variants_ab["variants"]) == 3
    assert result.variants_ab["variante_recommandee"]
    assert result.agent_results["agent_19"].status == AgentStatus.COMPLETED


def test_run_pydantic_valide(session_valide):
    result = asyncio.run(run(session_valide))
    VariantsAB.model_validate(result.variants_ab)


def test_run_sans_seo():
    session = SessionState(keyword="test", config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True))
    result = asyncio.run(run(session))
    assert len(result.variants_ab["variants"]) == 3


def test_variants_format_valide(session_valide):
    result = asyncio.run(run(session_valide))
    for v in result.variants_ab["variants"]:
        assert "title" in v
        assert "meta_description" in v
        assert 0 < v["ctr_predit"] <= 10


def test_recommandee_est_parmi_variants(session_valide):
    result = asyncio.run(run(session_valide))
    rec = result.variants_ab["variante_recommandee"]
    titles = [v["title"] for v in result.variants_ab["variants"]]
    assert rec in titles


def test_resultat_stocke(session_valide):
    result = asyncio.run(run(session_valide))
    assert result.agent_results["agent_19"].data == result.variants_ab


def test_mock_variants_trois():
    ab = _mock_variants(SessionState(keyword="test"))
    assert len(ab.variants) == 3
    assert ab.variante_recommandee


def test_mock_variants_ctr_varient():
    ab = _mock_variants(SessionState(keyword="test"))
    ctrs = [v.ctr_predit for v in ab.variants]
    assert len(set(ctrs)) >= 2  # Les CTR doivent etre differents


def test_predict_ctr_chiffre_mieux():
    ctr_avec = _predict_ctr("Les 5 meilleurs X en 2026", "Decouvrez notre guide.")
    ctr_sans = _predict_ctr("X", "Description.")
    assert ctr_avec > ctr_sans


def test_predict_ctr_longueur_ideale():
    ctr_court = _predict_ctr("Court", "")
    ctr_ideal = _predict_ctr("Guide Complet Assurance Vie 2026 | Expert", "Decouvrez tout.")
    assert ctr_ideal > ctr_court


def test_predict_ctr_dans_limites():
    ctr = _predict_ctr("Test", "Test")
    assert 0.5 <= ctr <= 10


def test_extract_json_valide():
    assert _extract_json('{"variants": []}') == {"variants": []}
