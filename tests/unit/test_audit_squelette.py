"""Audit complet du squelette Phase 1 — cohérence, imports, sérialisation."""

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hermes.models.common import (
    AgentStatus, QualityMode, SessionStatus, Intention, TypePage, Secteur,
    SECTEURS_REGLEMENTES, generate_session_id,
)
from hermes.models.session import AgentResult, SessionConfig, SessionState
from hermes.models.agent_data import (
    FicheEntreprise, SerpData, Brouillon, ScoresFinaux, GrilleScores,
    FactCheckData, ErreurFactuelle, SupervisorVerdict,
    IntentTypeData, TemplateData, SeoData, AeoBlocks, GeoData,
    EeatScore, ConformiteData, ExternalLinks, MultiformatData,
    VariantsAB, LocalisedData, SchemaData, ImagePlan, ExportData,
    RefreshPlan, FeedbackData, AntiCannibData, DifferenciationData,
    OffreConversion, FichePersona, InternalLinks,
)
from hermes.core.budget import BudgetTracker
from hermes.core.workflow import get_active_agents, AGENT_ORDER
from hermes.core.transitions import should_skip_agent, get_skip_warning
from hermes.core.llm import AGENT_TASK_TYPE, TASK_ROUTING, TaskType, LLMFactory


# ─── 1. Registre YAML vs fichiers réels ───────────────────────────────

def test_registry_yaml_valid():
    """agents_registry.yaml est un YAML valide avec 27 agents uniques."""
    path = Path(__file__).parent.parent.parent / "agents_registry.yaml"
    assert path.exists(), f"{path} introuvable"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "agents" in data
    assert len(data["agents"]) == 27
    ids = [a["id"] for a in data["agents"]]
    assert len(ids) == len(set(ids)), f"IDs dupliques: {ids}"


def test_registry_ids_match_agent_files():
    """Chaque agent du registre a un fichier Python existant."""
    root = Path(__file__).parent.parent.parent
    registry_path = root / "agents_registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    for agent in data["agents"]:
        agent_id = agent["id"]
        file_path = root / agent["file"]
        assert file_path.exists(), f"Fichier manquant pour {agent_id}: {file_path}"


def test_registry_ids_match_agent_order():
    """Les IDs du registre suivent AGENT_ORDER exactement."""
    root = Path(__file__).parent.parent.parent
    registry_path = root / "agents_registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    registry_ids = [a["id"] for a in data["agents"]]
    assert registry_ids == AGENT_ORDER


# ─── 2. Agents importables ────────────────────────────────────────────

def test_all_agent_modules_importable():
    """Les 27 modules agents sont importables et callable."""
    from hermes.agents import AGENT_REGISTRY
    assert len(AGENT_REGISTRY) == 27
    for agent_id in AGENT_ORDER:
        assert agent_id in AGENT_REGISTRY, f"Agent {agent_id} manquant dans AGENT_REGISTRY"
        fn = AGENT_REGISTRY[agent_id]
        assert callable(fn), f"Agent {agent_id} n'est pas callable"


# ─── 3. Routage LLM ───────────────────────────────────────────────────

def test_all_agents_have_task_type():
    """Chaque agent (sauf 00) a un TaskType defini."""
    for agent_id in AGENT_ORDER:
        if agent_id == "agent_00":
            continue
        assert agent_id in AGENT_TASK_TYPE, f"TaskType manquant pour {agent_id}"


def test_task_routing_complete():
    """Chaque TaskType a 3 modeles de routage."""
    for task_type in TaskType:
        assert task_type in TASK_ROUTING, f"Routage manquant pour {task_type}"
        models = TASK_ROUTING[task_type]
        assert len(models) == 3, f"{task_type} devrait avoir 3 modeles, a {len(models)}"


def test_llm_factory_select_model():
    """LLMFactory selectionne le bon modele selon le type de tache."""
    factory = LLMFactory(
        anthropic_api_key="test", openai_api_key="test",
        deepseek_api_key="test", dry_run=True,
    )
    assert factory.select_model("agent_09") == "claude-sonnet-4-6"  # REDACTION
    assert factory.select_model("agent_02") == "deepseek-v4-flash"  # LIGHT
    assert factory.select_model("agent_15", budget_tight=True) == "deepseek-v4-flash"


# ─── 4. Serialisation session ─────────────────────────────────────────

def test_session_round_trip():
    """SessionState peut etre serialisee et deserialisee sans perte."""
    original = SessionState(
        keyword="test audit",
        site_url="https://test.fr",
        config=SessionConfig(mode=QualityMode.PREMIUM, secteur="finance"),
        fiche_entreprise={"nom": "TestCorp", "secteur": "finance", "positionnement": "Leader"},
        brouillon_html="<h1>Test</h1>",
    )
    original.agent_results["agent_01"] = AgentResult(
        agent_id="agent_01", agent_name="Brief", status=AgentStatus.COMPLETED,
        tokens_input=100, tokens_output=50, cost_estimated=0.005,
    )
    restored = SessionState.model_validate_json(original.model_dump_json())
    assert restored.keyword == original.keyword
    assert restored.config.mode == QualityMode.PREMIUM
    assert restored.fiche_entreprise["nom"] == "TestCorp"
    assert restored.agent_results["agent_01"].status == AgentStatus.COMPLETED
    assert restored.agent_results["agent_01"].tokens_input == 100
    assert restored.session_id == original.session_id  # preserve


def test_session_json_size_reasonable(complete_session):
    """Une session complete tient dans moins de 100 Ko."""
    session = complete_session
    size_kb = len(session.model_dump_json()) / 1024
    assert size_kb < 100, f"Session trop volumineuse: {size_kb:.1f} KB"


# ─── 5. Budget ─────────────────────────────────────────────────────────

def test_budget_tracker_math():
    """Les calculs de cout sont corrects."""
    tracker = BudgetTracker(token_budget=100000, cost_budget=1.0)
    # DeepSeek V4 Flash : $0.14/$0.28 par million
    cost = tracker.estimate_cost("deepseek-v4-flash", 1000, 500)
    expected = (1000 / 1_000_000) * 0.14 + (500 / 1_000_000) * 0.28
    assert abs(cost - expected) < 0.0001
    # Claude Sonnet : $3/$15 par million
    cost2 = tracker.estimate_cost("claude-sonnet-4-6", 5000, 2000)
    expected2 = (5000 / 1_000_000) * 3.0 + (2000 / 1_000_000) * 15.0
    assert abs(cost2 - expected2) < 0.001
    assert 0.03 < cost2 < 0.06, f"Cout inattendu: ${cost2:.4f}"


def test_budget_can_proceed_blocks():
    """can_proceed bloque quand le budget est depasse."""
    tracker = BudgetTracker(token_budget=1000, cost_budget=0.01)
    ok, msg = tracker.can_proceed(100, 50, "deepseek-v4-flash")
    assert ok, f"Devrait passer: {msg}"
    ok2, msg2 = tracker.can_proceed(50000, 50000, "claude-opus-4-7")
    assert not ok2, f"Devrait bloquer: {msg2}"


def test_budget_warns_at_80_percent():
    """Alerte quand >80% du budget est consomme."""
    tracker = BudgetTracker(token_budget=1000000, cost_budget=0.10)
    tracker.cost_used = 0.07
    ok, msg = tracker.can_proceed(5000, 500, "claude-sonnet-4-6")
    assert ok
    assert "80%" in msg or "Alerte" in msg, f"Pas d'alerte: {msg}"


# ─── 6. Transitions ───────────────────────────────────────────────────

def test_should_skip_out_of_mode():
    """Un agent hors mode est skip auto."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.FAST, dry_run=True),
    )
    fast_agents = get_active_agents("fast")
    skip, reason, skip_type = should_skip_agent(
        "agent_02", session, set(fast_agents), False, False,
    )
    assert skip and skip_type == "auto"


def test_should_not_skip_mandatory():
    """Un agent obligatoire n'est jamais skip."""
    session = SessionState(
        keyword="test",
        config=SessionConfig(mode=QualityMode.FAST, dry_run=True),
    )
    fast_agents = get_active_agents("fast")
    skip, reason, skip_type = should_skip_agent(
        "agent_01", session, set(fast_agents), False, False,
    )
    assert not skip, f"Agent 01 ne devrait pas etre skip: {reason}"


def test_user_skip_generates_warning():
    """Un skip utilisateur a un message d'avertissement specifique."""
    warning = get_skip_warning("agent_02")
    # "ciblé" avec accent → on vérifie le radical sans l'accent
    assert "cibl" in warning.lower()


def test_all_skippable_agents_have_specific_warning():
    """Tous les agents skippables ont un avertissement specifique."""
    root = Path(__file__).parent.parent.parent
    registry_path = root / "agents_registry.yaml"
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    for agent in data["agents"]:
        if agent["skippable"]:
            warning = get_skip_warning(agent["id"])
            assert warning, f"Pas de warning pour {agent['id']}"
            is_generic = "etape non executee" in warning.lower()
            assert not is_generic, f"Warning generique pour {agent['id']}: {warning}"


# ─── 7. Modes qualite ─────────────────────────────────────────────────

def test_fast_mode_mandatory_agents():
    """Le mode fast contient les 9 agents essentiels."""
    fast = set(get_active_agents("fast"))
    mandatory = {"agent_00", "agent_01", "agent_04", "agent_07",
                 "agent_09", "agent_10", "agent_11", "agent_15", "agent_25"}
    assert mandatory.issubset(fast), f"Manquants: {mandatory - fast}"


def test_modes_are_strictly_increasing():
    """Chaque mode inclut le mode precedent."""
    fast = set(get_active_agents("fast"))
    std = set(get_active_agents("standard"))
    prem = set(get_active_agents("premium"))
    assert fast.issubset(std), f"Fast non inclus dans Standard: {fast - std}"
    assert std.issubset(prem), f"Standard non inclus dans Premium: {std - prem}"


def test_debug_mode_has_all_agents():
    """Le mode debug inclut tous les agents."""
    debug = get_active_agents("debug")
    assert len(debug) == 27
    assert set(debug) == set(AGENT_ORDER)


# ─── 8. Secteurs reglementes ──────────────────────────────────────────

def test_secteurs_reglementes_triggers_agent_14():
    """Agent 14 est inclus si le secteur est reglemente."""
    active = get_active_agents("standard", secteur="finance")
    assert "agent_14" in active


def test_secteurs_non_reglementes_skip_agent_14():
    """Agent 14 n'est pas inclus si le secteur n'est pas reglemente."""
    active = get_active_agents("standard", secteur="saas")
    assert "agent_14" not in active


# ─── 9. Couverture des modeles Pydantic ───────────────────────────────

AGENT_OUTPUT_MODELS = {
    "agent_00": SupervisorVerdict,
    "agent_01": FicheEntreprise,
    "agent_02": FichePersona,
    "agent_03": SerpData,
    "agent_04": IntentTypeData,
    "agent_05": OffreConversion,
    "agent_06": DifferenciationData,
    "agent_07": TemplateData,
    "agent_08": AntiCannibData,
    "agent_09": Brouillon,
    "agent_10": SeoData,
    "agent_11": AeoBlocks,
    "agent_12": GeoData,
    "agent_13": EeatScore,
    "agent_14": ConformiteData,
    "agent_15": FactCheckData,
    "agent_16": InternalLinks,
    "agent_17": ExternalLinks,
    "agent_18": MultiformatData,
    "agent_19": VariantsAB,
    "agent_20": LocalisedData,
    "agent_21": SchemaData,
    "agent_22": ImagePlan,
    "agent_23": ExportData,
    "agent_24": RefreshPlan,
    "agent_25": ScoresFinaux,
    "agent_26": FeedbackData,
}

def test_all_agents_have_output_model():
    """Chaque agent a un modele Pydantic de sortie defini."""
    for agent_id in AGENT_ORDER:
        if agent_id == "agent_00":
            continue
        assert agent_id in AGENT_OUTPUT_MODELS, f"Modele de sortie manquant pour {agent_id}"


# ─── 10. IDs et UUIDs ─────────────────────────────────────────────────

def test_session_ids_are_unique():
    """1000 sessions generees ont des IDs uniques."""
    ids = {generate_session_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_session_id_format():
    """L'ID de session fait 12 caracteres hex."""
    sid = generate_session_id()
    assert len(sid) == 12
    assert all(c in "0123456789abcdef" for c in sid)


# ─── 11. Validation des donnees mock ──────────────────────────────────

def test_fixture_complete_session_valid(complete_session):
    """La fixture complete_session passe la validation Pydantic."""
    session = complete_session
    assert session.keyword == "assurance vie temporaire"
    assert session.fiche_entreprise["secteur"] == "finance"
    assert session.brouillon_html is not None


def test_fixture_serp_data_valid():
    """La fixture SERP est un JSON valide."""
    path = Path(__file__).parent.parent / "fixtures" / "serp" / "response_google.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert "organic_results" in data
    assert len(data["organic_results"]) >= 5
