"""Tests unitaires — Pipeline Audit Technique (Sprint 1).

Couvre : modeles Pydantic, T00 Superviseur, T01 Crawler,
workflow, connecteurs security headers et hreflang.
"""

import asyncio
import pytest
from datetime import datetime

from hermes.models.audit_tech import (
    TechIssue, TechCrawlPage, TechDimensionScore,
    TechAuditScores, TechAuditState,
)
from hermes.agents.audit_tech.tt00_supervisor import run as tt00_run
from hermes.core.audit_tech_entry import init_tech_audit, resolve_tech_urls, CLIENT_PROFILES
from hermes.connectors.security_headers import check_security_headers, check_https_only
from hermes.connectors.hreflang_validator import extract_hreflang_tags, validate_hreflang_tags


# ═══════════════════════════════════════════════════════════════════════
# 1. Modeles Pydantic
# ═══════════════════════════════════════════════════════════════════════

class TestTechIssue:
    """Validation du modele TechIssue."""

    def test_issue_basique(self):
        issue = TechIssue(
            id="P-001",
            category="performance",
            description="Page trop lourde",
            url="https://example.com/lourde",
            observed="page_size_kb: 520",
            rule="page_size_kb > 500",
            confidence="high",
            source_agent="T07",
            severity="high",
            impact_business="Medium",
            gain_potentiel="High",
            effort="2h",
            priority="P1",
            cms_location="Serveur → Activer compression GZip",
        )
        assert issue.id == "P-001"
        assert issue.confidence == "high"
        assert issue.priority == "P1"

    def test_issue_defaults(self):
        issue = TechIssue(description="Test")
        assert issue.confidence == "medium"
        assert issue.priority == "P3"
        assert issue.impact_business == "Low"

    def test_issue_do_not_recommend(self):
        issue = TechIssue(
            id="P-002",
            category="content",
            description="Contenu court",
            url="https://example.com/cgu",
            observed="word_count: 120",
            rule="word_count < 200",
            do_not_recommend_if=["page_cgu", "page_panier"],
        )
        assert "page_cgu" in issue.do_not_recommend_if


class TestTechCrawlPage:
    """Validation du modele TechCrawlPage."""

    def test_page_defaults(self):
        page = TechCrawlPage(url="https://example.com")
        assert page.status_code == 200
        assert page.is_https is True
        assert page.is_indexable is True

    def test_page_signals(self):
        page = TechCrawlPage(
            url="https://example.com",
            title="Mon titre",
            title_length=9,
            h1="Mon H1",
            word_count=500,
            images_total=10,
            images_without_alt=3,
        )
        assert page.title == "Mon titre"
        assert page.images_without_alt == 3

    def test_page_to_dict(self):
        page = TechCrawlPage(url="https://example.com", title="Test")
        d = page.to_dict()
        assert d["url"] == "https://example.com"
        assert d["title"] == "Test"


class TestTechAuditState:
    """Validation du modele TechAuditState."""

    def test_state_init(self):
        state = TechAuditState(site_url="https://example.com", consent_given=True)
        assert state.site_url == "https://example.com"
        assert state.consent_given is True
        assert state.profile == "blog"
        assert state.status == "created"

    def test_state_scores_default(self):
        state = TechAuditState(site_url="https://example.com")
        assert state.scores.global_score == 0
        assert state.scores.performance.score == 0


class TestTechDimensionScore:
    """Validation du score par dimension."""

    def test_dimension_default(self):
        dim = TechDimensionScore()
        assert dim.score == 0
        assert dim.max_score == 100
        assert dim.confidence == "medium"

    def test_dimension_with_issues(self):
        dim = TechDimensionScore(score=75, confidence="high", issues_count=3, critical_count=1)
        assert dim.score == 75
        assert dim.critical_count == 1


# ═══════════════════════════════════════════════════════════════════════
# 2. T00 Superviseur
# ═══════════════════════════════════════════════════════════════════════

class TestT00Supervisor:
    """Tests du superviseur technique."""

    def test_consent_required(self):
        """Sans consentement, le superviseur bloque."""
        state = TechAuditState(site_url="https://example.com", consent_given=False)
        result = asyncio.run(tt00_run(state))
        assert result.status == "awaiting_consent"

    def test_consent_given(self):
        """Avec consentement, le superviseur initialise."""
        state = TechAuditState(
            site_url="https://example.com",
            consent_given=True,
            profile="blog",
        )
        result = asyncio.run(tt00_run(state))
        assert result.status == "consented"
        assert result.session_id.startswith("tech-")

    def test_domain_extraction(self):
        """Le domaine est extrait de l'URL."""
        state = TechAuditState(
            site_url="https://www.example.com",
            consent_given=True,
        )
        result = asyncio.run(tt00_run(state))
        assert result.domain == "example.com"

    def test_url_without_scheme(self):
        """Ajoute https:// si absent."""
        state = TechAuditState(site_url="example.com", consent_given=True)
        result = asyncio.run(tt00_run(state))
        assert result.site_url.startswith("https://")

    def test_bounds_clamping(self):
        """Les bornes sont plafonnees."""
        state = TechAuditState(
            site_url="https://example.com",
            consent_given=True,
            max_urls=10000,
            max_depth=20,
            rate_limit_rps=50,
        )
        result = asyncio.run(tt00_run(state))
        assert result.max_urls == 5000
        assert result.max_depth == 10
        assert result.rate_limit_rps == 10

    def test_invalid_profile_fallback(self):
        """Profil invalide → fallback blog."""
        state = TechAuditState(
            site_url="https://example.com",
            consent_given=True,
            profile="inconnu",
        )
        result = asyncio.run(tt00_run(state))
        assert result.profile == "blog"


# ═══════════════════════════════════════════════════════════════════════
# 3. Entry point
# ═══════════════════════════════════════════════════════════════════════

class TestAuditTechEntry:
    """Tests du point d'entree."""

    def test_init_tech_audit(self):
        state = asyncio.run(init_tech_audit(
            site_url="https://example.com",
            consent_given=True,
            profile="ecommerce",
        ))
        assert state.site_url == "https://example.com"
        assert state.profile == "ecommerce"
        assert state.consent_given is True
        assert state.status == "initialized"

    def test_init_with_urls(self):
        urls = ["https://example.com", "https://example.com/page"]
        state = asyncio.run(init_tech_audit(
            site_url="https://example.com",
            urls=urls,
            consent_given=True,
        ))
        assert len(state.urls) == 2

    def test_client_profiles_exist(self):
        """Les 5 profils client sont definis."""
        for p in ("ecommerce", "blog", "institutionnel", "agence", "saas"):
            assert p in CLIENT_PROFILES
            weights = CLIENT_PROFILES[p]
            total = weights["impact_seo"] + weights["impact_business"] + weights["effort"] + weights["conformite"]
            assert abs(total - 1.0) < 0.01, f"Profil {p}: poids = {total}"


# ═══════════════════════════════════════════════════════════════════════
# 4. Connecteurs
# ═══════════════════════════════════════════════════════════════════════

class TestSecurityHeaders:
    """Tests connecteur security headers."""

    def test_check_https(self):
        """Test HTTPS + redirect sur un site connu."""
        result = asyncio.run(check_https_only("https://www.google.com"))
        assert result["https_works"] is True
        # Verification de base : le site est accessible en HTTPS

    def test_security_headers_check(self):
        """Test analyse des headers de securite (site connu)."""
        result = asyncio.run(check_security_headers("https://www.google.com"))
        assert "score" in result
        assert "issues" in result
        assert len(result["issues"]) >= 6

    def test_invalid_url(self):
        """URL invalide → score 0, confidence low."""
        result = asyncio.run(check_security_headers("https://invalide-xyz-12345.invalid"))
        assert result["score"] == 0
        assert result["confidence"] == "low"


class TestHreflangValidator:
    """Tests connecteur hreflang."""

    def test_extract_no_hreflang(self):
        """HTML sans hreflang."""
        html = "<html><head></head><body></body></html>"
        tags = extract_hreflang_tags(html, "https://example.com")
        assert tags == []

    def test_extract_hreflang_tags(self):
        """HTML avec hreflang."""
        html = '''
        <html><head>
        <link rel="alternate" hreflang="fr" href="https://example.com/fr">
        <link rel="alternate" hreflang="en" href="https://example.com/en">
        <link rel="alternate" hreflang="x-default" href="https://example.com/">
        </head><body></body></html>
        '''
        tags = extract_hreflang_tags(html, "https://example.com")
        assert len(tags) == 3
        assert tags[0]["hreflang"] == "fr"

    def test_validate_valid_tags(self):
        """Tags valides → score 100."""
        tags = [
            {"hreflang": "fr", "href": "https://example.com/fr", "is_x_default": False},
            {"hreflang": "en", "href": "https://example.com/en", "is_x_default": False},
            {"hreflang": "x-default", "href": "https://example.com/", "is_x_default": True},
        ]
        result = validate_hreflang_tags(tags, "https://example.com/fr")
        assert result["score"] == 100
        assert result["errors"] == []

    def test_duplicate_hreflang(self):
        """Hreflang duplique → penalite."""
        tags = [
            {"hreflang": "fr", "href": "https://example.com/fr", "is_x_default": False},
            {"hreflang": "fr", "href": "https://example.com/fr2", "is_x_default": False},
        ]
        result = validate_hreflang_tags(tags, "https://example.com/fr")
        assert result["score"] < 100
        assert any("duplique" in e.lower() for e in result["errors"])

    def test_multiple_x_default(self):
        """Multiple x-default → penalite."""
        tags = [
            {"hreflang": "x-default", "href": "https://example.com/", "is_x_default": True},
            {"hreflang": "x-default", "href": "https://example.com/en", "is_x_default": True},
        ]
        result = validate_hreflang_tags(tags, "https://example.com/")
        assert result["score"] <= 75  # -25
        assert any("x-default" in e.lower() for e in result["errors"])

    def test_invalid_lang_code(self):
        """Code langue invalide → penalite."""
        tags = [
            {"hreflang": "francais", "href": "https://example.com/fr", "is_x_default": False},
        ]
        result = validate_hreflang_tags(tags, "https://example.com/fr")
        assert result["score"] < 100
        assert any("invalide" in e.lower() for e in result["errors"])


# ═══════════════════════════════════════════════════════════════════════
# 5. Workflow
# ═══════════════════════════════════════════════════════════════════════

class TestWorkflow:
    """Tests du workflow LangGraph."""

    def test_graph_builds(self):
        """Le graphe se construit sans erreur."""
        from hermes.core.audit_tech_workflow import build_tech_audit_graph
        graph = build_tech_audit_graph()
        assert graph is not None

    def test_workflow_blocks_without_consent(self):
        """Sans consentement, le workflow est bloque."""
        from hermes.core.audit_tech_workflow import run_tech_audit
        state = TechAuditState(site_url="https://example.com", consent_given=False)
        result = asyncio.run(run_tech_audit(state))
        assert result.status == "awaiting_consent"

    def test_workflow_blocks_without_urls(self):
        """Sans URLs, le workflow est bloque."""
        from hermes.core.audit_tech_workflow import run_tech_audit
        state = TechAuditState(
            site_url="https://example.com",
            consent_given=True,
            urls=[],
        )
        result = asyncio.run(run_tech_audit(state))
        assert result.status == "error"


# ═══════════════════════════════════════════════════════════════════════
# 6. Agent __init__ registry
# ═══════════════════════════════════════════════════════════════════════

class TestAgentRegistry:
    """Tests du registre d'agents."""

    def test_registry_has_agents(self):
        from hermes.agents.audit_tech import TECH_REGISTRY, TECH_ORDER
        assert "tt00" in TECH_REGISTRY
        assert "tt01" in TECH_REGISTRY
        assert TECH_ORDER[0] == "tt00"
        assert TECH_ORDER[1] == "tt01"

    def test_agents_are_callable(self):
        from hermes.agents.audit_tech import TECH_REGISTRY
        for agent_id, agent_fn in TECH_REGISTRY.items():
            assert callable(agent_fn), f"{agent_id} should be callable"


# ═══════════════════════════════════════════════════════════════════════
# 7. CMS Detection (reutilisation)
# ═══════════════════════════════════════════════════════════════════════

class TestCMSReuse:
    """Verifie que le CMS detector est reutilisable."""

    def test_cms_detector_importable(self):
        from hermes.connectors.cms_detector import detect_cms, CMS_SITEMAP_PRIORITY
        assert callable(detect_cms)
        assert "PrestaShop" in CMS_SITEMAP_PRIORITY
        assert "WordPress" in CMS_SITEMAP_PRIORITY
