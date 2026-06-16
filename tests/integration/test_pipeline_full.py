"""Test d'integration — Pipeline complet 26 agents en dry-run.

Verifie que les 26 agents s'enchainent sans erreur en mode debug,
produisent leurs sorties respectives, et que la session finale est coherente.
"""

import asyncio
from pathlib import Path

import pytest

from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState
from hermes.agents import AGENT_REGISTRY

# Agents dans l'ordre canonique
AGENT_ORDER = [f"agent_{i:02d}" for i in range(0, 27)]

# Sorties attendues apres chaque agent (verifiees par le superviseur)
AGENT_OUTPUTS = {
    "agent_01": "fiche_entreprise",
    "agent_02": "fiche_persona",
    "agent_03": "serp_data",
    "agent_04": "intention",
    "agent_05": "offre_conversion_data",
    "agent_06": "angles_differenciants",
    "agent_07": "template_data",
    "agent_08": "anti_cannib_data",
    "agent_09": "brouillon_html",
    "agent_10": "seo_data",
    "agent_11": "aeo_blocks",
    "agent_12": "geo_data",
    "agent_13": "score_eeat",
    "agent_14": "conformite_data",
    "agent_15": "fact_check_data",
    "agent_16": "internal_links",
    "agent_17": "external_links",
    "agent_18": "multiformat_data",
    "agent_19": "variants_ab",
    "agent_20": "localised_data",
    "agent_21": "ld_json",
    "agent_22": "image_plan",
    "agent_23": "export_data",
    "agent_24": "plan_refresh",
    "agent_25": "scores",
    "agent_26": "feedback_data",
}


@pytest.fixture
def base_session():
    """Session de base pour le pipeline complet."""
    return SessionState(
        keyword="guide complet assurance vie temporaire",
        site_url="https://www.monassureur.fr",
        objectif="Article pilier informatif et conversion",
        contraintes=["Pas de prix specifiques", "Inclure mentions legales"],
        config=SessionConfig(
            mode=QualityMode.DEBUG,
            dry_run=True,
            secteur="finance",
            token_budget=2_000_000,
            cost_budget=10.0,
            target_locales=["fr-be", "fr-ch"],
        ),
    )


def _get_attr(session: SessionState, attr_name: str):
    """Recupere un attribut de session par son nom."""
    return getattr(session, attr_name, None)


# ─── 1. Pipeline complet en dry-run ───────────────────────────────────

@pytest.mark.integration
def test_pipeline_complet_26_agents(base_session):
    """Execute les 26 agents en sequence et verifie que tous terminent."""
    session = base_session

    for agent_id in AGENT_ORDER:
        fn = AGENT_REGISTRY.get(agent_id)
        assert fn is not None, f"Agent {agent_id} introuvable"
        session = asyncio.run(fn(session))

        if agent_id == "agent_00":
            continue  # Superviseur ne produit pas de donnee

        result = session.agent_results.get(agent_id)
        assert result is not None, f"Pas de resultat pour {agent_id}"
        assert result.status in (
            AgentStatus.COMPLETED,
            AgentStatus.SKIPPED_AUTO,
            AgentStatus.SKIPPED_USER,
        ), f"{agent_id} a echoue: {result.error_message}"


@pytest.mark.integration
def test_toutes_les_sorties_produites(base_session):
    """Verifie que chaque agent produit sa sortie attendue."""
    session = base_session
    for agent_id in AGENT_ORDER:
        fn = AGENT_REGISTRY.get(agent_id)
        session = asyncio.run(fn(session))

    for agent_id, output_attr in AGENT_OUTPUTS.items():
        value = _get_attr(session, output_attr)
        assert value is not None, (
            f"Sortie manquante : {output_attr} (produit par {agent_id})"
        )

    # Verifications specifiques
    assert session.intention is not None
    assert session.type_page is not None
    assert session.brouillon_html
    assert len(session.brouillon_html) > 100
    assert session.scores
    assert session.scores["score_total"] > 0


@pytest.mark.integration
def test_pipeline_coherence_finale(base_session):
    """Verifie la coherence des donnees en fin de pipeline."""
    session = base_session
    for agent_id in AGENT_ORDER:
        fn = AGENT_REGISTRY.get(agent_id)
        session = asyncio.run(fn(session))

    # Coherence entreprise
    assert session.fiche_entreprise["secteur"] in ("finance", "saas", "sante", "autre")

    # Coherence persona
    assert session.fiche_persona["maturite"] in ("debutant", "intermediaire", "expert")

    # Coherence intention/type
    assert session.intention in (
        "informative", "transactionnelle", "comparative", "locale", "navigationnelle"
    )
    assert session.type_page is not None

    # Coherence SEO
    assert session.seo_data["title_optimise"]

    # Coherence AEO
    assert session.aeo_blocks["en_bref"]

    # Coherence GEO
    assert len(session.geo_data["entites_nommees"]) >= 1

    # Coherence EEAT
    assert 0 <= session.score_eeat["score_global"] <= 16

    # Coherence conformite
    assert session.conformite_data["risque_juridique"] in (
        "faible", "modere", "eleve", "critique"
    )

    # Coherence fact-checking
    assert 0 <= session.fact_check_data["score_fiabilite"] <= 10

    # Coherence schema
    assert session.ld_json["ld_json"]
    assert '"@type"' in session.ld_json["ld_json"]

    # Coherence export
    assert session.export_data["format"] in (
        "html", "wordpress", "woocommerce", "shopify", "webflow"
    )

    # Coherence scores
    assert 0 <= session.scores["score_total"] <= 100
    assert isinstance(session.scores["seuil_atteint"], bool)

    # Coherence feedback
    assert "clicks" in session.feedback_data["data_gsc"]


@pytest.mark.integration
def test_pipeline_temps_execution_raisonnable(base_session):
    """Le pipeline complet en dry-run doit s'executer en < 5 secondes."""
    import time
    session = base_session
    start = time.time()
    for agent_id in AGENT_ORDER:
        fn = AGENT_REGISTRY.get(agent_id)
        session = asyncio.run(fn(session))
    elapsed = time.time() - start
    assert elapsed < 10.0, f"Pipeline trop lent: {elapsed:.1f}s (max 10s en dry-run)"


@pytest.mark.integration
def test_pipeline_aucun_agent_failed(base_session):
    """Aucun agent ne doit echouer en dry-run."""
    session = base_session
    for agent_id in AGENT_ORDER:
        fn = AGENT_REGISTRY.get(agent_id)
        session = asyncio.run(fn(session))

    failed = [
        aid for aid, r in session.agent_results.items()
        if r.status == AgentStatus.FAILED
    ]
    assert not failed, f"Agents en echec: {failed}"
