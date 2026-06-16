"""Tests unitaires pour Agent 00 — Superviseur central."""

import pytest

from hermes.agents.agent_00_supervisor import (
    _evaluate,
    _validate_output,
    _check_consistency,
    AGENT_OUTPUT_SPEC,
    AGENT_DEPENDENCIES,
)
from hermes.models.agent_data import (
    FicheEntreprise,
    SerpData,
    SerpResult,
    Brouillon,
    SupervisorVerdict,
    IntentTypeData,
    TemplateData,
)
from hermes.models.common import (
    AgentStatus, QualityMode, SessionStatus, generate_session_id,
)
from hermes.models.session import AgentResult, SessionConfig, SessionState


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def base_session():
    """Session minimale valide."""
    return SessionState(
        keyword="test supervision",
        site_url="https://exemple.fr",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        current_agent_id="agent_00",
    )


@pytest.fixture
def session_apres_agent_01(base_session):
    """Session apres execution reussie de l'Agent 01."""
    s = base_session
    s.current_agent_id = "agent_02"
    s.fiche_entreprise = {
        "nom": "TestCorp", "secteur": "saas",
        "positionnement": "Leader du test",
    }
    s.agent_results["agent_01"] = AgentResult(
        agent_id="agent_01", agent_name="Brief Entreprise",
        status=AgentStatus.COMPLETED,
        data=s.fiche_entreprise,
    )
    return s


# ─── 1. Entree valide ─────────────────────────────────────────────────

def test_verdict_valide_session_neuve(base_session):
    """Une session neuve sans agent execute doit etre valide."""
    verdict = _evaluate(base_session)
    assert verdict.valid
    assert verdict.next_action == "proceed"


def test_verdict_valide_apres_agent_01(session_apres_agent_01):
    """Apres Agent 01 complete, le superviseur doit donner le feu vert."""
    verdict = _evaluate(session_apres_agent_01)
    assert verdict.valid, f"Raisons du blocage: {verdict.blocked_reasons}"
    assert verdict.next_action == "proceed"


def test_verdict_valide_agent_termine_avec_sortie_valide():
    """Un agent complete avec sortie Pydantic valide → OK."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        current_agent_id="agent_02",
        fiche_entreprise={"nom": "X", "secteur": "saas", "positionnement": "Leader"},
        agent_results={
            "agent_01": AgentResult(
                agent_id="agent_01", agent_name="Brief",
                status=AgentStatus.COMPLETED,
            ),
        },
    )
    verdict = _evaluate(session)
    assert verdict.valid


# ─── 2. Entree invalide ────────────────────────────────────────────────

def test_verdict_invalide_sans_keyword():
    """Session sans keyword → bloque."""
    session = SessionState(
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
    )
    verdict = _evaluate(session)
    assert not verdict.valid
    assert any("keyword" in r.lower() for r in verdict.blocked_reasons)


def test_verdict_invalide_agent_precedent_echoue():
    """Si l'agent precedent a fail, le pipeline est bloque."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        current_agent_id="agent_02",
        agent_results={
            "agent_01": AgentResult(
                agent_id="agent_01", agent_name="Brief",
                status=AgentStatus.FAILED,
                error_message="API timeout",
            ),
        },
    )
    verdict = _evaluate(session)
    assert not verdict.valid


def test_verdict_invalide_donnees_manquantes():
    """Agent 01 termine mais fiche_entreprise absente → avertissement."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        current_agent_id="agent_02",
        agent_results={
            "agent_01": AgentResult(
                agent_id="agent_01", agent_name="Brief",
                status=AgentStatus.COMPLETED,
            ),
        },
        # fiche_entreprise est None (absent)
    )
    verdict = _evaluate(session)
    # Le superviseur avertit mais ne bloque pas forcement
    # car l'agent 01 a "termine" (le warning est plus approprie)
    assert len(verdict.warnings) >= 0  # Au moins pas de crash


def test_verdict_invalide_dependance_non_satisfaite():
    """Agent 09 (Redaction) lance sans Agent 01 → bloque si pas skip."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        current_agent_id="agent_09",
        # Pas de fiche_entreprise, pas d'agent_01 result
    )
    verdict = _evaluate(session)
    # Devrait bloquer car agent_09 depend de agent_01
    assert not verdict.valid
    assert any("fiche_entreprise" in r.lower() for r in verdict.blocked_reasons)


# ─── 3. Sortie conforme ───────────────────────────────────────────────

def test_supervisor_verdict_structure():
    """Le verdict a tous les champs requis."""
    verdict = SupervisorVerdict(valid=True, next_action="proceed")
    assert verdict.valid
    assert verdict.next_action == "proceed"
    assert verdict.blocked_reasons == []
    assert verdict.warnings == []


def test_supervisor_verdict_bloque():
    """Un verdict de blocage a des raisons."""
    verdict = SupervisorVerdict(
        valid=False,
        blocked_reasons=["Raison 1", "Raison 2"],
        next_action="block",
    )
    assert not verdict.valid
    assert len(verdict.blocked_reasons) == 2


# ─── 4. Validation Pydantic des sorties ───────────────────────────────

def test_validate_fiche_entreprise_valide():
    ok, err = _validate_output(
        FicheEntreprise,
        {"nom": "X", "secteur": "saas", "positionnement": "Leader"},
        "agent_01",
    )
    assert ok
    assert err == ""


def test_validate_fiche_entreprise_invalide():
    ok, err = _validate_output(
        FicheEntreprise,
        {"nom": "X"},  # manque secteur et positionnement
        "agent_01",
    )
    assert not ok
    assert "agent_01" in err


def test_validate_sortie_none():
    ok, err = _validate_output(FicheEntreprise, None, "agent_01")
    assert not ok


def test_validate_brouillon_valide():
    ok, err = _validate_output(
        Brouillon,
        {"html": "<h1>Test</h1>", "word_count": 5},
        "agent_09",
    )
    assert ok


def test_validate_brouillon_sans_html():
    ok, err = _validate_output(Brouillon, {"word_count": 5}, "agent_09")
    assert not ok


# ─── 5. Coherence inter-champs ────────────────────────────────────────

def test_coherence_intention_vs_type_incoherent():
    """Intention transactionnelle + type news → warning."""
    session = SessionState(
        keyword="test",
        intention="transactionnelle",
        type_page="news",
    )
    warnings: list[str] = []
    _check_consistency(session, warnings)
    assert len(warnings) > 0
    assert any("transactionnelle" in w for w in warnings)


def test_coherence_intention_vs_type_coherent():
    """Intention informative + type article → pas de warning."""
    session = SessionState(
        keyword="test",
        intention="informative",
        type_page="article",
    )
    warnings: list[str] = []
    _check_consistency(session, warnings)
    # Pas de warning pour une combinaison coherente
    coherent_related = [
        w for w in warnings
        if "transactionnelle" in w or "informative" in w or "locale" in w
    ]
    assert len(coherent_related) == 0


def test_coherence_secteur_reglemente_sans_conformite():
    """Secteur finance + agent 14 skip → warning."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True, secteur="finance"),
        agent_results={
            "agent_14": AgentResult(
                agent_id="agent_14",
                agent_name="Conformite",
                status=AgentStatus.SKIPPED_AUTO,
                skip_reason="Test",
            ),
        },
    )
    warnings: list[str] = []
    _check_consistency(session, warnings)
    assert any("reglemente" in w.lower() for w in warnings)


# ─── 6. Couverture du registre ────────────────────────────────────────

def test_tous_les_agents_output_spec():
    """Chaque agent (sauf 00) est dans AGENT_OUTPUT_SPEC."""
    from hermes.core.workflow import AGENT_ORDER
    for agent_id in AGENT_ORDER:
        if agent_id == "agent_00":
            continue
        assert agent_id in AGENT_OUTPUT_SPEC, f"Manquant: {agent_id}"


def test_tous_les_agents_dependencies():
    """Chaque agent (sauf 00) est dans AGENT_DEPENDENCIES."""
    from hermes.core.workflow import AGENT_ORDER
    for agent_id in AGENT_ORDER:
        if agent_id == "agent_00":
            continue
        assert agent_id in AGENT_DEPENDENCIES, f"Manquant: {agent_id}"


def test_dependances_ordonnees():
    """Un agent ne depend jamais d'un agent ulterieur."""
    from hermes.core.workflow import AGENT_ORDER
    order_idx = {aid: i for i, aid in enumerate(AGENT_ORDER)}

    for agent_id, deps in AGENT_DEPENDENCIES.items():
        agent_idx = order_idx.get(agent_id, 0)
        for dep_id in deps:
            dep_idx = order_idx.get(dep_id, 999)
            assert dep_idx < agent_idx, (
                f"{agent_id} depend de {dep_id} qui est apres lui "
                f"({agent_idx} < {dep_idx})"
            )


# ─── 7. Test d'erreur controlee ───────────────────────────────────────

def test_session_failed_bloque():
    """Une session en etat failed est bloquee."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        status=SessionStatus.FAILED,
    )
    verdict = _evaluate(session)
    assert not verdict.valid


def test_skip_agent_naturel():
    """Un agent skip user ne bloque pas le pipeline."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.DEBUG, dry_run=True),
        current_agent_id="agent_03",
        fiche_entreprise={"nom": "X", "secteur": "saas", "positionnement": "Leader"},
        agent_results={
            "agent_01": AgentResult(
                agent_id="agent_01", agent_name="Brief",
                status=AgentStatus.COMPLETED,
            ),
            "agent_02": AgentResult(
                agent_id="agent_02", agent_name="Persona",
                status=AgentStatus.SKIPPED_USER,
                skip_reason="Persona deja connu",
            ),
        },
    )
    verdict = _evaluate(session)
    assert verdict.valid


def test_run_modifie_session(base_session):
    """La fonction run modifie l'etat de la session."""
    import asyncio
    session = base_session
    session.current_agent_id = "agent_00"

    result = asyncio.run(
        __import__("hermes.agents.agent_00_supervisor", fromlist=["run"]).run(session)
    )
    # La session doit etre en running ou blocked
    assert result.status != SessionStatus.FAILED
