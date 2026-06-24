"""Tests P7 (Maintenance) + P8 (Learning Engine)."""

import pytest
from hermes.models.project import (
    Project, ExecutionAction, ConsolidatedRecommendation,
    DISCLAIMERS, ONBOARDING_STEPS,
)
from hermes.agents.maintenance import MAINTENANCE_REGISTRY
from hermes.agents.learning import LEARNING_REGISTRY


@pytest.fixture
def project():
    return Project(
        nom="Test Projet", site_url="https://test.fr", domain="test.fr",
        profile="local", secteur="autre",
        competitors=["concurrent.fr"], keywords_cibles=["test"],
    )


# ─── P7 Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_m00_startup(project):
    result = await MAINTENANCE_REGISTRY["m00"](project)
    assert result.max_actions_per_day == 20
    assert result.actions_executed_today == 0


@pytest.mark.asyncio
async def test_m01_decay(project):
    project.max_actions_per_day = 20
    result = await MAINTENANCE_REGISTRY["m01"](project)
    assert "decay_pages" in result.local_seo


@pytest.mark.asyncio
async def test_m02_core_update(project):
    project.max_actions_per_day = 20
    result = await MAINTENANCE_REGISTRY["m02"](project)
    assert isinstance(result.execution_actions, list)


@pytest.mark.asyncio
async def test_m03_dispatcher(project):
    project.max_actions_per_day = 20
    project.execution_actions = [
        ExecutionAction(source_pipeline="m01", source_agent="m01", category="optimize",
                       action_type="content_refresh", description="Test", priority="P1"),
        ExecutionAction(source_pipeline="p5", source_agent="st06", category="generate",
                       action_type="creer_pilier", description="Creer pilier SEO", priority="P1"),
    ]
    result = await MAINTENANCE_REGISTRY["m03"](project)
    assert len(result.recommandations) > 0
    assert result.next_action


@pytest.mark.asyncio
async def test_m04_generator(project):
    project.max_actions_per_day = 20
    project.execution_actions = [
        ExecutionAction(source_pipeline="m03", category="generate", action_type="generer_llms_txt",
                       description="Generer llms.txt", status="pending"),
        ExecutionAction(source_pipeline="m03", category="generate", action_type="generer_disavow",
                       description="Generer Disavow", status="pending"),
    ]
    result = await MAINTENANCE_REGISTRY["m04"](project)
    executed = [a for a in result.execution_actions if a.status == "executed"]
    assert len(executed) >= 1
    assert executed[0].content_to_generate


@pytest.mark.asyncio
async def test_m05_optimizer_human_review(project):
    project.max_actions_per_day = 20
    project.execution_actions = [
        ExecutionAction(source_pipeline="m03", category="optimize", action_type="enrichir_eeat",
                       description="Enrichir EEAT", status="pending"),
    ]
    result = await MAINTENANCE_REGISTRY["m05"](project)
    for a in result.execution_actions:
        if a.category == "optimize":
            assert a.human_approval_required is True


@pytest.mark.asyncio
async def test_m06_publisher(project):
    project.max_actions_per_day = 20
    project.execution_actions = [
        ExecutionAction(source_pipeline="m03", category="publish", action_type="publier_cms",
                       description="Publier CMS", status="pending", human_approval_required=False),
    ]
    result = await MAINTENANCE_REGISTRY["m06"](project)
    executed = [a for a in result.execution_actions if a.status == "executed"]
    assert len(executed) >= 1


@pytest.mark.asyncio
async def test_m07_monitor(project):
    project.execution_actions = [
        ExecutionAction(source_pipeline="m04", category="generate", action_type="generer_llms_txt",
                       status="executed", executed_at="2026-06-01T00:00:00"),
    ]
    result = await MAINTENANCE_REGISTRY["m07"](project)
    assert result is not None  # Impact monitor should run


# V1.5 agents
@pytest.mark.asyncio
async def test_m08_safety(project):
    result = await MAINTENANCE_REGISTRY["m08"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_m09_rollback(project):
    project.execution_actions = [
        ExecutionAction(status="failed", snapshot_before={"html": "old", "taken_at": "2026-06-01"}),
    ]
    result = await MAINTENANCE_REGISTRY["m09"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_m10_dependencies(project):
    result = await MAINTENANCE_REGISTRY["m10"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_m11_approval(project):
    project.execution_actions = [
        ExecutionAction(action_type="generer_llms_txt", status="pending"),
        ExecutionAction(action_type="enrichir_eeat", status="pending", confidence_before=50),
    ]
    result = await MAINTENANCE_REGISTRY["m11"](project)
    auto = [a for a in result.execution_actions if not a.human_approval_required]
    manual = [a for a in result.execution_actions if a.human_approval_required]
    assert len(auto) >= 1
    assert len(manual) >= 1


# ─── P8 Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_l00_supervisor(project):
    result = await LEARNING_REGISTRY["l00"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_l01_calibrator_accumulation(project):
    result = await LEARNING_REGISTRY["l01"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_l02_patterns(project):
    result = await LEARNING_REGISTRY["l02"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_l03_delay(project):
    result = await LEARNING_REGISTRY["l03"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_l04_update_classifier(project):
    result = await LEARNING_REGISTRY["l04"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_l05_model_distributor(project):
    result = await LEARNING_REGISTRY["l05"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_l06_library(project):
    result = await LEARNING_REGISTRY["l06"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_l07_optimizer(project):
    result = await LEARNING_REGISTRY["l07"](project)
    assert result is not None


@pytest.mark.asyncio
async def test_l08_failure_analyzer(project):
    result = await LEARNING_REGISTRY["l08"](project)
    assert result is not None


# ─── Model Tests ────────────────────────────────────────────────────

def test_project_model():
    p = Project(nom="Test", site_url="https://test.fr", domain="test.fr")
    assert p.id
    assert p.max_actions_per_day == 20
    assert p.mode_execution == "semi-auto"
    assert p.human_approval_threshold == 60


def test_disclaimers_all_present():
    assert len(DISCLAIMERS) == 8
    expected_ids = {"perf", "delais", "donnees", "ia", "ymyl", "concurrence", "budget", "non_substitution"}
    actual_ids = {d.get("id") for d in DISCLAIMERS.values()}
    assert actual_ids == expected_ids, f"IDs manquants: {expected_ids - actual_ids}"


def test_onboarding_steps():
    assert len(ONBOARDING_STEPS) == 8
    steps_names = [s["step"] for s in ONBOARDING_STEPS]
    assert "welcome" in steps_names
    assert "complete" in steps_names


def test_execution_action():
    a = ExecutionAction(category="generate", action_type="generer_llms_txt",
                       description="Test", human_approval_required=False)
    assert a.id
    assert a.category == "generate"


def test_consolidated_recommendation():
    r = ConsolidatedRecommendation(sujet="Test", description="Desc",
                                   action_concrete="Faire X", action_executable="generer_x")
    assert r.id
    assert r.requires_human is False  # Par defaut


# ─── Pipeline Complet P7 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_p7_pipeline(project):
    project.max_actions_per_day = 20
    project.mode_execution = "semi-auto"
    project.execution_actions = [
        ExecutionAction(source_pipeline="p5", category="generate",
                       action_type="creer_pilier", description="Creer un pilier SEO",
                       priority="P1", status="pending"),
    ]
    from hermes.agents.maintenance import MAINTENANCE_ORDER
    for agent_id in MAINTENANCE_ORDER:
        if agent_id in MAINTENANCE_REGISTRY:
            project = await MAINTENANCE_REGISTRY[agent_id](project)
    assert project.max_actions_per_day >= 1
    assert len(project.execution_actions) > 0


# ─── Pipeline Complet P8 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_p8_pipeline(project):
    from hermes.agents.learning import LEARNING_ORDER
    for agent_id in LEARNING_ORDER:
        if agent_id in LEARNING_REGISTRY:
            project = await LEARNING_REGISTRY[agent_id](project)
    assert project is not None
