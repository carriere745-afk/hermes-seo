"""Tests d'integration — Reprise apres erreur et simulation d'echec.

Verifie que le pipeline peut s'arreter proprement et reprendre
depuis le dernier agent reussi sans recommencer depuis le debut.
"""

import asyncio

import pytest

from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState
from hermes.agents import AGENT_REGISTRY

AGENT_ORDER = [f"agent_{i:02d}" for i in range(0, 27)]


@pytest.fixture
def session_minimale():
    return SessionState(
        keyword="test reprise pipeline",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="saas"),
        brouillon_html="<h1>Test</h1><p>Contenu pour reprise.</p>",
    )


@pytest.mark.integration
def test_reprise_apres_echec_simule():
    """Simule un echec a l'agent 05 et verifie la reprise."""
    session = SessionState(
        keyword="test reprise",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="saas"),
    )

    # Executer jusqu'a l'agent 04 normalement
    for agent_id in ["agent_00", "agent_01", "agent_02", "agent_03", "agent_04"]:
        fn = AGENT_REGISTRY.get(agent_id)
        session = asyncio.run(fn(session))
        assert session.agent_results[agent_id].status in (
            AgentStatus.COMPLETED, AgentStatus.SKIPPED_AUTO
        ), f"{agent_id} a echoue: {session.agent_results[agent_id].error_message}"

    # Verifier que les 4 premiers agents ont bien produit leurs sorties
    assert session.fiche_entreprise is not None
    assert session.fiche_persona is not None
    assert session.serp_data is not None
    assert session.intention is not None

    # Simuler un echec a l'agent 05
    session.agent_results["agent_05"] = AgentResult(
        agent_id="agent_05", agent_name="Offre & Conversion",
        status=AgentStatus.FAILED,
        error_message="API timeout simule",
    )
    session.error_count = 1

    # Maintenant "reprendre" depuis l'agent 05
    # En pratique, on re-execute agent_05 qui overwrite le resultat
    fn_05 = AGENT_REGISTRY.get("agent_05")
    session = asyncio.run(fn_05(session))
    assert session.agent_results["agent_05"].status == AgentStatus.COMPLETED

    # Continuer avec le reste du pipeline
    start_idx = AGENT_ORDER.index("agent_06")
    for agent_id in AGENT_ORDER[start_idx:]:
        fn = AGENT_REGISTRY.get(agent_id)
        session = asyncio.run(fn(session))

    # Verifier que tout le pipeline a termine
    for agent_id in AGENT_ORDER:
        if agent_id in ("agent_00", "agent_08", "agent_17", "agent_18",
                        "agent_19", "agent_20", "agent_24", "agent_26"):
            continue  # Peuvent etre skippes
        result = session.agent_results.get(agent_id)
        if result:
            assert result.status != AgentStatus.FAILED, (
                f"{agent_id} en echec apres reprise: {result.error_message}"
            )


@pytest.mark.integration
def test_reprise_depuis_agent_specifique():
    """Rejoue depuis l'agent 09 (Redaction) avec un etat deja rempli."""
    session = SessionState(
        keyword="test reprise mi-parcours",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        fiche_entreprise={
            "nom": "TestCorp", "secteur": "finance",
            "positionnement": "Leader du test",
        },
        fiche_persona={
            "nom_persona": "Paul", "maturite": "intermediaire",
        },
        serp_data={
            "top10": [{"position": 1, "title": "T1", "url": "u1", "snippet": "s1", "domain": "d1.fr"}],
            "paa": ["Q1?"],
            "concurrents_directs": ["site1.fr"],
        },
        intention="informative",
        type_page="article",
        offre_conversion_data={
            "benefices": ["B1"], "objections": ["O1"],
            "cta_principal": "Essayez",
        },
        angles_differenciants={
            "angle_principal": "Angle test",
            "facteurs_differenciation": ["F1"],
        },
        template_data={
            "template_id": "article",
            "structure": [
                {"type": "h1", "titre": "Test", "contenu_guide": "...", "obligatoire": True, "ordre": 0},
                {"type": "intro", "titre": "Intro", "contenu_guide": "...", "obligatoire": True, "ordre": 1},
                {"type": "conclusion", "titre": "Fin", "contenu_guide": "...", "obligatoire": True, "ordre": 2},
            ],
            "nb_sections": 3,
        },
    )

    # Marquer les agents 00-08 comme completes
    for aid in AGENT_ORDER[:9]:
        session.agent_results[aid] = AgentResult(
            agent_id=aid, agent_name=aid, status=AgentStatus.COMPLETED,
        )

    # Executer de 09 a 26
    start_idx = AGENT_ORDER.index("agent_09")
    for agent_id in AGENT_ORDER[start_idx:]:
        fn = AGENT_REGISTRY.get(agent_id)
        session = asyncio.run(fn(session))

    # Verifier que la redaction a bien produit un brouillon
    assert session.agent_results["agent_09"].status == AgentStatus.COMPLETED
    assert session.brouillon_html
    assert len(session.brouillon_html) > 100

    # Verifier que les scores finaux sont presents
    assert session.scores is not None
    assert session.scores["score_total"] > 0


@pytest.mark.integration
def test_session_incomplete_relancable():
    """Une session avec des agents manquants peut etre completee."""
    # Session partielle : seulement agents 01-05 executes
    session = SessionState(
        keyword="test session incomplete",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="saas"),
    )

    # Executer les 6 premiers agents (00-05)
    for agent_id in AGENT_ORDER[:6]:
        fn = AGENT_REGISTRY.get(agent_id)
        session = asyncio.run(fn(session))

    # Verifier l'etat intermediaire
    assert session.fiche_entreprise is not None
    assert session.offre_conversion_data is not None
    assert session.brouillon_html is None  # Pas encore de redaction

    # Sauvegarder et recharger simules
    saved = session.model_dump_json()
    restored = SessionState.model_validate_json(saved)

    assert restored.fiche_entreprise == session.fiche_entreprise
    assert restored.last_completed_agent_id == session.last_completed_agent_id

    # Continuer avec le reste du pipeline
    for agent_id in AGENT_ORDER[6:]:
        fn = AGENT_REGISTRY.get(agent_id)
        restored = asyncio.run(fn(restored))

    # Verifier que tout est complete
    assert restored.brouillon_html is not None
    assert restored.scores is not None
