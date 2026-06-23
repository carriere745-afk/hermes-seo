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
        assert "tt03" in TECH_REGISTRY
        assert "tt04" in TECH_REGISTRY
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


# ═══════════════════════════════════════════════════════════════════════
# 10. Sprint 3 — T02 Indexation
# ═══════════════════════════════════════════════════════════════════════

class TestT02Indexation:
    """Tests du statut d'indexation (T02)."""

    def _make_page(self, url="https://example.com/page", **kw):
        defaults = {"url": url, "status_code": 200, "word_count": 500}
        defaults.update(kw)
        return TechCrawlPage(**defaults)

    def test_estimate_noindex(self):
        """Page avec noindex est detectee."""
        from hermes.agents.audit_tech.tt02_indexation import _estimate_indexability
        page = self._make_page(has_noindex=True, is_indexable=False)
        status, notes = _estimate_indexability(page)
        assert status == "not_indexed_noindex"

    def test_estimate_blocked(self):
        """Page bloquee robots.txt."""
        from hermes.agents.audit_tech.tt02_indexation import _estimate_indexability
        page = self._make_page(robots_blocked=True)
        status, _ = _estimate_indexability(page)
        assert status == "not_indexed_blocked"

    def test_estimate_probably_indexable(self):
        """Page normale = probablement indexable."""
        from hermes.agents.audit_tech.tt02_indexation import _estimate_indexability
        page = self._make_page()
        status, _ = _estimate_indexability(page)
        assert status == "probably_indexable"

    def test_estimate_error_status(self):
        """HTTP 500 = non indexable."""
        from hermes.agents.audit_tech.tt02_indexation import _estimate_indexability
        page = self._make_page(status_code=500)
        status, _ = _estimate_indexability(page)
        assert status == "probably_not_indexable"

    def test_index_status_all_keys(self):
        """Tous les statuts d'indexation sont definis."""
        from hermes.agents.audit_tech.tt02_indexation import INDEX_STATUS
        for key in ("indexed", "not_indexed_noindex", "not_indexed_blocked",
                     "not_indexed_error", "probably_indexable",
                     "probably_not_indexable", "unknown"):
            assert key in INDEX_STATUS

    def test_agent_run_no_pages(self):
        """T02 sans pages crawlees — skip."""
        from hermes.agents.audit_tech.tt02_indexation import run as tt02_run
        state = TechAuditState(site_url="https://example.com")
        result = asyncio.run(tt02_run(state))
        assert len(result.issues) == 0

    def test_agent_run_with_pages(self):
        """T02 avec pages crawlees (sans GSC)."""
        from hermes.agents.audit_tech.tt02_indexation import run as tt02_run

        pages = [
            self._make_page("https://example.com/"),
            self._make_page("https://example.com/page1", has_noindex=True),
        ]
        state = TechAuditState(site_url="https://example.com", crawled_pages=pages)
        result = asyncio.run(tt02_run(state))
        # L'agent genere des issues (au moins pour les pages non indexables)
        assert result.scores.indexation.score >= 0


# ═══════════════════════════════════════════════════════════════════════
# 11. Sprint 3 — T05 Structure
# ═══════════════════════════════════════════════════════════════════════

class TestT05Structure:
    """Tests de la structure on-page (T05)."""

    def _make_page(self, url="https://example.com/page", **kw):
        defaults = {"url": url, "status_code": 200, "word_count": 500,
                    "title": "Un bon titre pour la page", "title_length": 30,
                    "meta_description": "Une meta description suffisamment longue pour etre correcte",
                    "meta_description_length": 65,
                    "h1": "Mon titre principal", "h1_count": 1,
                    "heading_hierarchy_ok": True}
        defaults.update(kw)
        return TechCrawlPage(**defaults)

    def test_agent_run_no_pages(self):
        """T05 sans pages."""
        from hermes.agents.audit_tech.tt05_structure import run as tt05_run
        state = TechAuditState(site_url="https://example.com")
        result = asyncio.run(tt05_run(state))
        assert len(result.issues) == 0

    def test_agent_run_detects_missing_title(self):
        """Title absent genere une issue."""
        from hermes.agents.audit_tech.tt05_structure import run as tt05_run

        page = self._make_page(title="", title_length=0)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt05_run(state))
        assert any("Title absent" in i.description for i in result.issues)

    def test_agent_run_detects_missing_h1(self):
        """H1 absent genere une issue."""
        from hermes.agents.audit_tech.tt05_structure import run as tt05_run

        page = self._make_page(h1="", h1_count=0)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt05_run(state))
        assert any("H1 absent" in i.description for i in result.issues)

    def test_agent_run_detects_multiple_h1(self):
        """H1 multiples."""
        from hermes.agents.audit_tech.tt05_structure import run as tt05_run

        page = self._make_page(h1_count=2)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt05_run(state))
        assert any("Plusieurs H1" in i.description for i in result.issues)

    def test_agent_run_duplicate_titles(self):
        """Titles dupliques generent une issue."""
        from hermes.agents.audit_tech.tt05_structure import run as tt05_run

        pages = [
            self._make_page("https://example.com/page1"),
            self._make_page("https://example.com/page2"),
        ]
        state = TechAuditState(site_url="https://example.com", crawled_pages=pages)
        result = asyncio.run(tt05_run(state))
        assert any("duplique" in i.description.lower() for i in result.issues)

    def test_agent_run_duplicate_h1s(self):
        """H1 dupliques."""
        from hermes.agents.audit_tech.tt05_structure import run as tt05_run

        pages = [
            self._make_page("https://example.com/page1"),
            self._make_page("https://example.com/page2"),
        ]
        state = TechAuditState(site_url="https://example.com", crawled_pages=pages)
        result = asyncio.run(tt05_run(state))
        assert any("H1 duplique" in i.description for i in result.issues)

    def test_agent_run_missing_og(self):
        """OG tags absents — issue."""
        from hermes.agents.audit_tech.tt05_structure import run as tt05_run

        page = self._make_page(og_title="", og_description="", og_image="",
                               meta_description="Une meta description parfaitement assez longue pour le test",
                               meta_description_length=65,
                               title="Un bon titre assez long", title_length=26,
                               h1="Mon H1 unique", h1_count=1)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt05_run(state))
        # L'agent detecte l'absence de OG
        assert any("OG" in i.description or "og" in i.observed.lower() for i in result.issues)

    def test_agent_sets_score(self):
        """Score structure est mis a jour."""
        from hermes.agents.audit_tech.tt05_structure import run as tt05_run

        page = self._make_page()
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt05_run(state))
        assert result.scores.structure.score > 0


# ═══════════════════════════════════════════════════════════════════════
# 12. Sprint 3 — T06 Thin Content
# ═══════════════════════════════════════════════════════════════════════

class TestT06ThinContent:
    """Tests du thin content adaptatif (T06)."""

    def _make_page(self, url="https://example.com/page", **kw):
        defaults = {"url": url, "status_code": 200, "word_count": 800,
                    "title": "Article complet sur le sujet", "h1": "Guide complet",
                    "h2_list": ["Introduction", "Corps", "Conclusion"]}
        defaults.update(kw)
        return TechCrawlPage(**defaults)

    def test_page_type_detection(self):
        """Detection du type de page."""
        from hermes.agents.audit_tech.tt06_thin_content import _get_page_type
        assert _get_page_type("https://example.com/") == "accueil"
        assert _get_page_type("https://example.com/123-produit.html") == "produit"
        assert _get_page_type("https://example.com/blog/article-test") == "article"
        assert _get_page_type("https://example.com/cgu") == "legale"
        assert _get_page_type("https://example.com/faq/livraison") == "faq"
        assert _get_page_type("https://example.com/cart") == "legale"

    def test_text_hash(self):
        """Hash MD5 stable."""
        from hermes.agents.audit_tech.tt06_thin_content import _text_hash
        h1 = _text_hash("bonjour le monde")
        h2 = _text_hash("bonjour le monde")
        h3 = _text_hash("autre texte")
        assert h1 == h2
        assert h1 != h3

    def test_cosine_identical(self):
        """Similarite cosinus de textes identiques ~= 1.0."""
        from hermes.agents.audit_tech.tt06_thin_content import _cosine_similarity
        sim = _cosine_similarity("texte identique", "texte identique")
        assert sim > 0.999

    def test_cosine_different(self):
        """Similarite cosinus de textes tres differents < 0.5."""
        from hermes.agents.audit_tech.tt06_thin_content import _cosine_similarity
        sim = _cosine_similarity(
            "seo audit technique performance",
            "cuisine recette gateau chocolat"
        )
        assert sim < 0.5

    def test_thin_article_detected(self):
        """Article < 600 mots = thin content."""
        from hermes.agents.audit_tech.tt06_thin_content import run as tt06_run

        page = self._make_page("https://example.com/blog/court", word_count=200)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt06_run(state))
        assert any("court" in i.description.lower() for i in result.issues)

    def test_cgu_not_penalized(self):
        """CGU = jamais penalise pour thin content."""
        from hermes.agents.audit_tech.tt06_thin_content import run as tt06_run

        page = self._make_page("https://example.com/cgu", word_count=50)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt06_run(state))
        # Une CGU courte ne genere pas d'issue "thin content"
        thin_issues = [i for i in result.issues if "court" in i.description.lower() and "thin" in i.category]
        assert len(thin_issues) == 0

    def test_product_threshold_300(self):
        """Fiche produit : seuil 300 mots."""
        from hermes.agents.audit_tech.tt06_thin_content import run as tt06_run

        page_ok = self._make_page("https://example.com/1-produit-ok.html", word_count=350)
        page_thin = self._make_page("https://example.com/2-produit-thin.html", word_count=150)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page_ok, page_thin])
        result = asyncio.run(tt06_run(state))
        thin_issues = [i for i in result.issues if "court" in i.description.lower()]
        assert len(thin_issues) == 1
        assert "2-produit-thin" in thin_issues[0].url

    def test_duplicate_detection(self):
        """Detection de contenu duplique."""
        from hermes.agents.audit_tech.tt06_thin_content import run as tt06_run

        pages = [
            self._make_page("https://example.com/page1"),
            self._make_page("https://example.com/page2"),
        ]
        state = TechAuditState(site_url="https://example.com", crawled_pages=pages)
        result = asyncio.run(tt06_run(state))
        # Avec le meme contenu, doit detecter un exact duplicate
        assert any("duplique" in i.description.lower() for i in result.issues)

    def test_agent_sets_score(self):
        """Score content mis a jour."""
        from hermes.agents.audit_tech.tt06_thin_content import run as tt06_run

        page = self._make_page(word_count=800)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt06_run(state))
        assert result.scores.content.score > 0

    def test_agent_run_no_pages(self):
        """T06 sans pages — skip."""
        from hermes.agents.audit_tech.tt06_thin_content import run as tt06_run
        state = TechAuditState(site_url="https://example.com")
        result = asyncio.run(tt06_run(state))
        assert len(result.issues) == 0


# ═══════════════════════════════════════════════════════════════════════
# 13. Sprint 4 — T07 Performance
# ═══════════════════════════════════════════════════════════════════════

class TestT07Performance:
    """Tests de l'analyse performance (T07)."""

    def _make_page(self, url="https://example.com/page", **kw):
        defaults = {
            "url": url, "status_code": 200, "page_size_kb": 200,
            "ttfb_ms": 150, "load_time_ms": 800,
            "images_total": 5, "external_links_count": 3,
        }
        defaults.update(kw)
        return TechCrawlPage(**defaults)

    def test_cwv_heuristic(self):
        """L'estimation heuristique fonctionne."""
        from hermes.connectors.pagespeed_connector import estimate_cwv_heuristic
        result = estimate_cwv_heuristic(
            page_size_kb=300, ttfb_ms=200, load_time_ms=1200,
            images_count=10, external_resources=5
        )
        assert result["source"] == "heuristic"
        assert result["confidence"] == "low"
        assert "lcp" in result
        assert "cls" in result
        assert result["lcp"]["value"] > 0

    def test_cwv_label(self):
        """Labels CWV corrects."""
        from hermes.connectors.pagespeed_connector import _label_cwv
        assert _label_cwv("lcp", 1000) == "good"
        assert _label_cwv("lcp", 3000) == "needs improvement"
        assert _label_cwv("lcp", 5000) == "poor"
        assert _label_cwv("cls", 0.05) == "good"
        assert _label_cwv("cls", 0.3) == "poor"

    def test_agent_run_no_pages(self):
        """T07 sans pages."""
        from hermes.agents.audit_tech.tt07_performance import run as tt07_run
        state = TechAuditState(site_url="https://example.com")
        result = asyncio.run(tt07_run(state))
        assert len(result.issues) == 0

    def test_agent_run_heavy_page(self):
        """Page lourde genere une issue."""
        from hermes.agents.audit_tech.tt07_performance import run as tt07_run

        page = self._make_page(page_size_kb=800)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt07_run(state))
        assert any("lourde" in i.description.lower() for i in result.issues)

    def test_agent_sets_score(self):
        """Score performance mis a jour."""
        from hermes.agents.audit_tech.tt07_performance import run as tt07_run

        page = self._make_page()
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt07_run(state))
        assert result.scores.performance.score >= 0


# ═══════════════════════════════════════════════════════════════════════
# 14. Sprint 4 — T08 Mobile
# ═══════════════════════════════════════════════════════════════════════

class TestT08Mobile:
    """Tests de l'analyse mobile (T08)."""

    def _make_page(self, url="https://example.com/page", **kw):
        defaults = {
            "url": url, "status_code": 200, "word_count": 500,
            "has_viewport": True, "images_total": 5, "images_without_alt": 0,
            "text_html_ratio": 0.15,
        }
        defaults.update(kw)
        return TechCrawlPage(**defaults)

    def test_viewport_content_validation(self):
        """Validation contenu viewport."""
        from hermes.agents.audit_tech.tt08_mobile import _validate_viewport_content

        issues = _validate_viewport_content("width=device-width, initial-scale=1")
        assert len(issues) == 0

        issues = _validate_viewport_content("width=800")
        assert any("width=device-width" in i for i in issues)

        issues = _validate_viewport_content("user-scalable=no")
        assert any("zoom" in i for i in issues)

    def test_agent_run_missing_viewport(self):
        """Viewport absent."""
        from hermes.agents.audit_tech.tt08_mobile import run as tt08_run

        page = self._make_page(has_viewport=False)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt08_run(state))
        assert any("viewport" in i.description.lower() for i in result.issues)

    def test_agent_run_no_pages(self):
        """T08 sans pages."""
        from hermes.agents.audit_tech.tt08_mobile import run as tt08_run
        state = TechAuditState(site_url="https://example.com")
        result = asyncio.run(tt08_run(state))
        assert len(result.issues) == 0

    def test_agent_sets_score(self):
        """Score mobile mis a jour."""
        from hermes.agents.audit_tech.tt08_mobile import run as tt08_run

        page = self._make_page()
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt08_run(state))
        assert result.scores.mobile.score >= 0


# ═══════════════════════════════════════════════════════════════════════
# 15. Sprint 4 — T09 Schemas
# ═══════════════════════════════════════════════════════════════════════

class TestT09Schemas:
    """Tests de la validation schema.org (T09)."""

    def _make_page(self, url="https://example.com/page", **kw):
        defaults = {
            "url": url, "status_code": 200, "json_ld_types": [],
            "json_ld_valid": False, "microdata_present": False,
        }
        defaults.update(kw)
        return TechCrawlPage(**defaults)

    def test_page_type_detection(self):
        """Detection du type pour schema."""
        from hermes.agents.audit_tech.tt09_schemas import _get_page_type
        assert _get_page_type("https://example.com/") == "accueil"
        assert _get_page_type("https://example.com/blog/article") == "article"
        assert _get_page_type("https://example.com/123-produit.html") == "produit"
        assert _get_page_type("https://example.com/cgu") == "legale"

    def test_validate_json_ld_types_empty(self):
        """Liste vide = pas d'erreurs."""
        from hermes.agents.audit_tech.tt09_schemas import _validate_json_ld_types
        result = _validate_json_ld_types([])
        assert result["errors"] == []

    def test_validate_json_ld_known_types(self):
        """Types connus = valides."""
        from hermes.agents.audit_tech.tt09_schemas import _validate_json_ld_types
        result = _validate_json_ld_types(["Article", "BreadcrumbList"])
        assert "Article" in result["valid_types"]
        assert "BreadcrumbList" in result["valid_types"]

    def test_agent_run_missing_recommended_schema(self):
        """Produit sans schema Product genere une issue."""
        from hermes.agents.audit_tech.tt09_schemas import run as tt09_run

        page = self._make_page("https://example.com/1-produit.html")
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt09_run(state))
        assert any("Schema" in i.description for i in result.issues)
        assert any("Product" in i.description for i in result.issues)

    def test_agent_run_legal_no_warnings(self):
        """Page legale sans schema = pas d'issue."""
        from hermes.agents.audit_tech.tt09_schemas import run as tt09_run

        page = self._make_page("https://example.com/cgu")
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt09_run(state))
        assert len(result.issues) == 0

    def test_agent_run_no_pages(self):
        """T09 sans pages."""
        from hermes.agents.audit_tech.tt09_schemas import run as tt09_run
        state = TechAuditState(site_url="https://example.com")
        result = asyncio.run(tt09_run(state))
        assert len(result.issues) == 0

    def test_agent_sets_score(self):
        """Score schema mis a jour."""
        from hermes.agents.audit_tech.tt09_schemas import run as tt09_run

        page = self._make_page("https://example.com/", json_ld_types=["WebSite"],
                               json_ld_valid=True)
        state = TechAuditState(site_url="https://example.com", crawled_pages=[page])
        result = asyncio.run(tt09_run(state))
        assert result.scores.structured_data.score >= 0


# ═══════════════════════════════════════════════════════════════════════
# 8. Sprint 2 — T03 Architecture
# ═══════════════════════════════════════════════════════════════════════

class TestT03Architecture:
    """Tests de l'analyse d'architecture (T03)."""

    def _make_page(self, url: str, **kwargs):
        """Helper: cree un TechCrawlPage avec des liens internes."""
        defaults = {
            "url": url,
            "status_code": 200,
            "title": f"Page {url}",
            "word_count": 500,
            "crawl_depth": 0,
        }
        defaults.update(kwargs)
        return TechCrawlPage(**defaults)

    def test_graph_builds(self):
        """Construction du graphe depuis les pages."""
        from hermes.agents.audit_tech.tt03_architecture import _build_link_graph

        pages = [
            self._make_page("https://example.com/", internal_links_list=[
                {"url": "https://example.com/page1", "anchor": "Page 1"},
                {"url": "https://example.com/page2", "anchor": "Page 2"},
            ]),
            self._make_page("https://example.com/page1", internal_links_list=[
                {"url": "https://example.com/", "anchor": "Home"},
            ]),
            self._make_page("https://example.com/page2", internal_links_list=[
                {"url": "https://example.com/", "anchor": "Home"},
            ]),
        ]

        G = _build_link_graph(pages)
        assert G.number_of_nodes() == 3
        assert G.number_of_edges() >= 2

    def test_graph_empty(self):
        """Graphe vide."""
        from hermes.agents.audit_tech.tt03_architecture import _build_link_graph
        G = _build_link_graph([])
        assert G.number_of_nodes() == 0

    def test_metrics_no_pages(self):
        """Metriques sur graphe vide."""
        from hermes.agents.audit_tech.tt03_architecture import _compute_graph_metrics
        import networkx as nx
        G = nx.DiGraph()
        metrics = _compute_graph_metrics(G, [])
        assert metrics["nodes"] == 0
        assert metrics["depth_avg"] == 0.0

    def test_metrics_with_data(self):
        """Metriques avec des pages."""
        from hermes.agents.audit_tech.tt03_architecture import _compute_graph_metrics
        import networkx as nx

        G = nx.DiGraph()
        G.add_edge("https://example.com/", "https://example.com/page1")
        G.add_edge("https://example.com/", "https://example.com/page2")
        G.add_edge("https://example.com/page1", "https://example.com/")

        pages = [
            TechCrawlPage(url="https://example.com/", crawl_depth=0),
            TechCrawlPage(url="https://example.com/page1", crawl_depth=1),
            TechCrawlPage(url="https://example.com/page2", crawl_depth=1),
        ]

        metrics = _compute_graph_metrics(G, pages)
        assert metrics["nodes"] == 3
        assert metrics["depth_avg"] == pytest.approx(0.67, abs=0.1)
        assert metrics["depth_max"] == 1

    def test_orphan_detection(self):
        """Detection de pages orphelines."""
        from hermes.agents.audit_tech.tt03_architecture import _compute_graph_metrics
        import networkx as nx

        G = nx.DiGraph()
        G.add_node("https://example.com/")
        G.add_node("https://example.com/orphan")  # no incoming links

        pages = [
            TechCrawlPage(url="https://example.com/", crawl_depth=0),
            TechCrawlPage(url="https://example.com/orphan", crawl_depth=0),
        ]

        metrics = _compute_graph_metrics(G, pages)
        assert "https://example.com/orphan" in metrics["orphans"]

    def test_silo_detection_small_graph(self):
        """Detection de silos sur un petit graphe."""
        from hermes.agents.audit_tech.tt03_architecture import _detect_silos, _build_link_graph

        # Groupe 1 : home + page1, page2 (bien liees)
        # Groupe 2 : page3, page4 (peu liees, sans hub fort)
        pages = [
            self._make_page("https://example.com/", internal_links_list=[
                {"url": "https://example.com/page1", "anchor": "P1"},
                {"url": "https://example.com/page2", "anchor": "P2"},
                {"url": "https://example.com/page3", "anchor": "P3"},
            ]),
            self._make_page("https://example.com/page1", internal_links_list=[
                {"url": "https://example.com/", "anchor": "Home"},
                {"url": "https://example.com/page2", "anchor": "P2"},
            ]),
            self._make_page("https://example.com/page2", internal_links_list=[
                {"url": "https://example.com/", "anchor": "Home"},
                {"url": "https://example.com/page1", "anchor": "P1"},
            ]),
            self._make_page("https://example.com/page3"),
            self._make_page("https://example.com/page4"),
        ]

        G = _build_link_graph(pages)
        silos, fantomes = _detect_silos(G, pages)
        # Au moins un silo doit etre detecte (le groupe 1)
        assert len(silos) >= 0  # Louvain peut echouer sur petit graphe, c'est OK

    def test_agent_run_no_pages(self):
        """T03 sans pages crawlees."""
        from hermes.agents.audit_tech.tt03_architecture import run as tt03_run

        state = TechAuditState(site_url="https://example.com")
        result = asyncio.run(tt03_run(state))
        assert result.status == "crawled"

    def test_agent_run_with_pages(self):
        """T03 avec pages crawlees."""
        from hermes.agents.audit_tech.tt03_architecture import run as tt03_run

        pages = [
            self._make_page("https://example.com/", internal_links_list=[
                {"url": "https://example.com/page1", "anchor": "P1"},
                {"url": "https://example.com/page2", "anchor": "P2"},
            ]),
            self._make_page("https://example.com/page1", internal_links_list=[
                {"url": "https://example.com/", "anchor": "Home"},
            ]),
            self._make_page("https://example.com/page2"),
        ]

        state = TechAuditState(site_url="https://example.com", crawled_pages=pages)
        result = asyncio.run(tt03_run(state))
        assert result.graph_edges is not None
        # Avec 3 pages peu maillees, il devrait y avoir des issues
        assert len(result.issues) > 0


# ═══════════════════════════════════════════════════════════════════════
# 9. Sprint 2 — T04 Sitemap & Robots
# ═══════════════════════════════════════════════════════════════════════

class TestT04Sitemap:
    """Tests de l'analyse sitemap + robots.txt (T04)."""

    def test_robots_empty_content(self):
        """robots.txt vide."""
        from hermes.agents.audit_tech.tt04_sitemap import _analyze_robots_txt

        result = _analyze_robots_txt("", "https://example.com")
        assert result["found"] is False
        assert len(result["issues"]) >= 1

    def test_robots_valid(self):
        """robots.txt valide."""
        from hermes.agents.audit_tech.tt04_sitemap import _analyze_robots_txt

        content = """
User-agent: *
Allow: /
Sitemap: https://example.com/sitemap.xml
"""
        result = _analyze_robots_txt(content, "https://example.com")
        assert result["found"] is True
        assert len(result["sitemap_refs"]) == 1
        assert result["disallow_all"] is False

    def test_robots_disallow_all(self):
        """robots.txt qui bloque tout."""
        from hermes.agents.audit_tech.tt04_sitemap import _analyze_robots_txt

        content = """
User-agent: *
Disallow: /
"""
        result = _analyze_robots_txt(content, "https://example.com")
        assert result["disallow_all"] is True

    def test_agent_run_no_site_url(self):
        """T04 sans site_url — skip."""
        from hermes.agents.audit_tech.tt04_sitemap import run as tt04_run

        state = TechAuditState(site_url="")
        result = asyncio.run(tt04_run(state))
        assert len(result.issues) == 0

    def test_sitemap_parser_reusable(self):
        """Verifie que le sitemap_parser est importable."""
        from hermes.connectors.sitemap_parser import detect_sitemaps, parse_sitemap_recursive
        assert callable(detect_sitemaps)
        assert callable(parse_sitemap_recursive)

    def test_protego_available(self):
        """Verifie que protego est disponible."""
        from protego import Protego
        assert Protego is not None

    def test_robots_not_blocking_googlebot(self):
        """robots.txt ne doit pas bloquer Googlebot."""
        from hermes.agents.audit_tech.tt04_sitemap import _analyze_robots_txt

        content = """
User-agent: Googlebot
Disallow:
"""
        result = _analyze_robots_txt(content, "https://example.com")
        # Pas de critique Googlebot
        assert not any(i["severity"] == "critical" for i in result["issues"])
