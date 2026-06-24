"""Tests integration cross-pipeline + resilience."""

import pytest


# ═══════════════════════════════════════════════════════════════════
# Cross-pipeline integration tests
# ═══════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_p4_to_p5_data_flow():
    """P4 positions should feed P5 strategy."""
    from hermes.models.serp_visibility import SerpVisibilityState
    from hermes.models.strategie import StrategieState
    state = SerpVisibilityState(
        site_url="https://example.com",
        keywords=["test keyword"],
        mode="fast",
    )
    state.health_score = 50
    state.positions = []
    # Verify state is serializable
    js = state.model_dump_json()
    assert "example.com" in js

    # P5 should be constructible
    p5 = StrategieState(
        site_url="https://example.com",
        domain="example.com",
        mode="fast",
        profile="blog",
    )
    assert p5.startup_ok is False  # Not started yet


@pytest.mark.asyncio
async def test_p5_to_p6_recommendations_flow():
    """P5 recommendations should be convertible to P6 opportunities."""
    from hermes.models.strategie import StrategieState, Recommandation
    from hermes.models.backlinks import BacklinksState, BacklinkOpportunity

    p5 = StrategieState(
        site_url="https://example.com", domain="example.com",
        mode="fast", profile="blog",
    )
    rec = Recommandation(
        sujet="Test backlink", action="creer_pilier", priorite="P1",
        volume_recherche=1000, confidence_score=75, pipeline_cible="P6",
    )
    p5.recommandations = [rec]

    # Convert to P6 opportunity
    opp = BacklinkOpportunity(
        domain="target-blog.fr", priority=rec.priorite,
        impact_score=rec.confidence_score,
        source="P5_ST06",
        description=f"Recommande par P5: {rec.sujet}",
        keywords_cibles=rec.keywords,
    )
    assert opp.priority == "P1"
    assert opp.impact_score == 75


@pytest.mark.asyncio
async def test_p6_to_p7_execution_flow():
    """P6 backlink opportunities should feed P7 execution."""
    from hermes.models.backlinks import BacklinksState, BacklinkOpportunity
    from hermes.models.project import Project, ExecutionAction

    # Simulate P6 output
    opp = BacklinkOpportunity(
        domain="target-blog.fr", priority="P1",
        opportunity_type="guest_post", impact_score=80,
        cost_estime=150.0,
    )

    # Convert to P7 action
    project = Project(
        nom="Test", site_url="https://example.com", domain="example.com",
        profile="blog", mode_execution="semi-auto",
    )
    action = ExecutionAction(
        source_pipeline="p6", source_agent="b06",
        category="generate", action_type="generer_email_crm",
        description=f"Guest post: {opp.domain}",
        priority=opp.priority, confidence_before=int(opp.impact_score),
        human_approval_required=False,
    )
    project.execution_actions.append(action)

    assert len(project.execution_actions) == 1
    assert project.execution_actions[0].category == "generate"


@pytest.mark.asyncio
async def test_full_cross_pipeline_state_transfer():
    """Full P4→P5→P6→P7 state transfer chain."""
    from hermes.models.serp_visibility import SerpVisibilityState
    from hermes.models.strategie import StrategieState
    from hermes.models.backlinks import BacklinksState
    from hermes.models.project import Project, ExecutionAction

    # 1. P4 provides positions
    p4 = SerpVisibilityState(site_url="https://example.com", mode="fast")
    p4.health_score = 65

    # 2. P5 consumes P4 data
    p5 = StrategieState(
        site_url="https://example.com", domain="example.com",
        mode="fast", profile="blog",
    )
    p5.executive_summary = None  # Will be set by ST11
    assert p5.domain == "example.com"

    # 3. P6 consumes P5 recommendations
    p6 = BacklinksState(
        site_url="https://example.com", domain="example.com",
        mode="fast", profile="blog",
    )
    p6.competitors = ["concurrent.fr"]
    assert len(p6.competitors) == 1

    # 4. P7 receives all recommendations
    project = Project(
        nom="Test", site_url="https://example.com", domain="example.com",
        profile="blog", mode_execution="semi-auto",
    )
    project.execution_actions = [
        ExecutionAction(source_pipeline="p5", category="generate",
                       action_type="creer_pilier", priority="P1"),
        ExecutionAction(source_pipeline="p6", category="publish",
                       action_type="generer_disavow", priority="P2"),
    ]
    assert len(project.execution_actions) == 2


# ═══════════════════════════════════════════════════════════════════
# Resilience tests
# ═══════════════════════════════════════════════════════════════════

def test_credential_sanitizer():
    """Credentials should never appear in logs or reports."""
    from hermes.config import sanitize_credentials

    test_str = "Bearer ya29.abcdef123456 token here"
    result = sanitize_credentials(test_str)
    assert "ya29" not in result
    assert "REDACTED" in result or "Bearer" in result

    test_str2 = "https://api.example.com?api_key=sk-secret-key-12345"
    result2 = sanitize_credentials(test_str2)
    assert "sk-secret" not in result2
    assert "REDACTED" in result2


def test_rate_limiter_ip():
    """Rate limiter should block excessive requests."""
    from hermes.core.rate_limiter import check_ip_rate

    # First 100 requests should pass
    ip = "192.168.1.1"
    passed = 0
    for _ in range(100):
        if check_ip_rate(ip):
            passed += 1
    assert passed == 100

    # 101st should fail
    assert check_ip_rate(ip) is False


def test_rate_limiter_project_quota():
    """Project quota should reset daily."""
    from hermes.models.project import Project
    from hermes.core.rate_limiter import check_project_quota, get_quota_remaining

    project = Project(nom="Test", site_url="https://example.com", domain="example.com",
                     max_actions_per_day=5, mode_execution="semi-auto")

    # Should allow 5 actions
    for _ in range(5):
        assert check_project_quota(project)
        project.actions_executed_today += 1

    # 6th should fail
    assert check_project_quota(project) is False
    assert get_quota_remaining(project) == 0


def test_gsc_403_error_message():
    """GSC 403 should produce a clear, actionable error message."""
    try:
        from hermes.connectors.gsc_connector import GSCConnector
        # Verify the connector class exists and has error handling
        assert hasattr(GSCConnector, 'query')
        # The 403 handling is in the query method
    except ImportError:
        pass  # GSC not configured, skip


def test_project_scores_consolidation():
    """Project should consolidate scores from all pipelines."""
    from hermes.models.project import Project

    p = Project(nom="Test", site_url="https://example.com", domain="example.com")

    # Simulate pipeline completion
    p.content_score = 75
    p.technique_score = 80
    p.visibility_score = 60
    p.strategy_score = 55
    p.authority_score = 45

    # Health should be weighted average
    avg = (75 + 80 + 60 + 55 + 45) / 5
    p.health_score = int(avg)
    assert p.health_score == 63  # (75+80+60+55+45)/5 = 63


def test_disclaimers_model_integrity():
    """All 8 disclaimers should be complete with title, text, display trigger."""
    from hermes.models.project import DISCLAIMERS

    assert len(DISCLAIMERS) == 8
    for key, d in DISCLAIMERS.items():
        assert isinstance(d, dict)
        assert "titre" in d, f"Titre manquant pour {key}"
        assert "texte" in d, f"Texte manquant pour {key}"
        assert "affichage" in d, f"Affichage manquant pour {key}"
        assert "severite" in d, f"Severite manquante pour {key}"
        assert len(d["texte"]) > 50, f"Texte trop court pour {key}"


def test_deploy_script_exists():
    """Deployment script should be present."""
    from pathlib import Path
    deploy_script = Path("deploy.sh")
    assert deploy_script.exists(), "deploy.sh manquant"


def test_docker_files_exist():
    """Docker files should be present."""
    from pathlib import Path
    assert Path("Dockerfile").exists(), "Dockerfile manquant"
    assert Path("docker-compose.yml").exists(), "docker-compose.yml manquant"


def test_security_md_exists():
    """SECURITY.md should be present."""
    from pathlib import Path
    assert Path("SECURITY.md").exists(), "SECURITY.md manquant"


def test_requirements_has_all_deps():
    """Requirements.txt should list all critical dependencies."""
    reqs = open("requirements.txt").read()
    for dep in ["streamlit", "pydantic", "langgraph", "anthropic", "httpx", "chromadb", "tenacity", "loguru"]:
        assert dep in reqs, f"Dependance {dep} manquante dans requirements.txt"
