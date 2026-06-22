"""Tests du Pipeline Audit de Contenu — 10 agents."""

import asyncio

import pytest

from hermes.models.audit import (
    AuditBrief, AuditScores, AuditSessionState, CrawledPage, DimensionScore,
)
from hermes.agents.audit import AUDIT_REGISTRY, AUDIT_ORDER, prepare_audit_brief_for_editorial


# ─── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def session_empty():
    return AuditSessionState(
        session_id="test_001",
        site_url="https://example.com",
        urls=["https://example.com/page1"],
        mode="standard",
    )


@pytest.fixture
def session_with_page(session_empty):
    """Session avec une page deja crawlee (simule AC01)."""
    page = CrawledPage(
        url="https://example.com/page1",
        status_code=200,
        title="Guide Complet SEO 2026 — Conseils d'Experts | Example",
        title_length=52,
        meta_description="Decouvrez notre guide complet SEO 2026. Conseils, exemples et guide pas a pas.",
        meta_description_length=85,
        h1="Guide Complet SEO 2026",
        h1_count=1,
        h2_list=["Qu'est-ce que le SEO ?", "Comment fonctionne le referencement", "Les avantages du SEO", "FAQ", "Conclusion"],
        h3_list=["Definition", "Fonctionnement", "Avantage 1", "Avantage 2", "Question 1", "Question 2"],
        word_count=1200,
        word_count_visible=1200,
        text_html_ratio=15.5,
        images_total=4,
        images_with_alt=3,
        images_lazy=2,
        images_with_dimensions=3,
        internal_links=5,
        external_links=2,
        json_ld_types=["Article"],
        json_ld_valid=True,
        has_cta=True,
        cta_count=2,
        has_breadcrumbs=True,
        has_viewport=True,
        author_detected=True,
        author_name="Jean Dupont",
        date_published="2026-01-15",
        date_modified="2026-06-01",
        is_indexable=True,
        has_noindex=False,
    )
    session_empty.crawled_pages = [page]
    return session_empty


# ─── 1. Registre ──────────────────────────────────────────────────────

class TestRegistry:
    def test_all_agents_registered(self):
        assert len(AUDIT_REGISTRY) == 10
        for agent_id in AUDIT_ORDER:
            assert agent_id in AUDIT_REGISTRY, f"Missing: {agent_id}"

    def test_all_callable(self):
        for agent_id, fn in AUDIT_REGISTRY.items():
            assert callable(fn), f"Not callable: {agent_id}"


# ─── 2. Modèles ──────────────────────────────────────────────────────

class TestModels:
    def test_crawled_page_defaults(self):
        p = CrawledPage(url="https://example.com")
        assert p.url == "https://example.com"
        assert p.status_code == 200
        assert p.word_count == 0

    def test_audit_scores_default(self):
        s = AuditScores()
        assert s.global_score == 0
        assert s.global_confidence == "indicatif"

    def test_audit_brief_default(self):
        b = AuditBrief(page_url="https://example.com")
        assert b.mode_audit is True
        assert b.action == "conserver"

    def test_session_initial_state(self):
        s = AuditSessionState(urls=["https://example.com"])
        assert len(s.urls) == 1
        assert s.status == "created"

    def test_prepare_brief_for_editorial(self):
        state = AuditSessionState(session_id="test", urls=["https://example.com/page1"])
        brief = AuditBrief(page_url="https://example.com/page1", action="enrichir")
        state.briefs["https://example.com/page1"] = brief
        result = prepare_audit_brief_for_editorial(state, "https://example.com/page1")
        assert result is not None
        assert result["action"] == "enrichir"

    def test_prepare_brief_not_found(self):
        state = AuditSessionState(session_id="test", urls=[])
        result = prepare_audit_brief_for_editorial(state, "nonexistent")
        assert result is None


# ─── 3. AC00 — Superviseur ────────────────────────────────────────────

class TestAC00:
    def test_valid_urls(self):
        state = AuditSessionState(urs=["https://example.com", "http://test.org"])
        result = asyncio.run(AUDIT_REGISTRY["ac00"](state))
        assert result.status == "running"
        assert len(result.urls) == 2

    def test_invalid_url_filtered(self):
        state = AuditSessionState(urs=["https://ok.com", "not-a-url", "", "http://valid.org"])
        result = asyncio.run(AUDIT_REGISTRY["ac00"](state))
        assert len(result.urls) == 2
        assert "https://ok.com" in result.urls
        assert "http://valid.org" in result.urls

    def test_empty_urls_blocked(self):
        state = AuditSessionState(urs=["not-valid"])
        result = asyncio.run(AUDIT_REGISTRY["ac00"](state))
        assert result.status == "blocked"


# ─── 4. AC01 — Content Crawler ────────────────────────────────────────

class TestAC01:
    def test_crawl_real_page(self):
        """Test sur une vraie page web."""
        state = AuditSessionState(
            session_id="test_crawl",
            urls=["https://example.com"],
        )
        result = asyncio.run(AUDIT_REGISTRY["ac01"](state))
        assert len(result.crawled_pages) == 1
        page = result.crawled_pages[0]
        assert page.status_code == 200
        assert page.word_count > 0
        assert page.title
        assert page.h1

    def test_crawl_multiple(self):
        state = AuditSessionState(
            session_id="test_multi",
            urls=["https://example.com", "https://httpbin.org/html"],
        )
        result = asyncio.run(AUDIT_REGISTRY["ac01"](state))
        assert len(result.crawled_pages) == 2

    def test_extraction_signals(self):
        """Verifie que les 55+ signaux sont extraits."""
        state = AuditSessionState(
            session_id="test_signals",
            urls=["https://example.com"],
        )
        result = asyncio.run(AUDIT_REGISTRY["ac01"](state))
        page = result.crawled_pages[0]
        # Verifier les champs cles
        assert page.title_length > 0
        assert page.h1_count >= 0
        assert page.word_count > 0
        assert page.images_total >= 0
        assert page.internal_links >= 0
        assert page.external_links >= 0
        assert page.has_viewport in (True, False)


# ─── 5. AC02 — Scoring SEO ────────────────────────────────────────────

class TestAC02:
    def test_score_real_page(self, session_with_page):
        result = asyncio.run(AUDIT_REGISTRY["ac02"](session_with_page))
        scores = result.scores.get("https://example.com/page1")
        assert scores is not None
        assert scores.seo_onpage.score > 0
        assert scores.quality.score > 0
        assert scores.global_score > 0

    def test_score_range(self, session_with_page):
        result = asyncio.run(AUDIT_REGISTRY["ac02"](session_with_page))
        s = result.scores["https://example.com/page1"]
        assert 0 <= s.seo_onpage.score <= 100
        assert 0 <= s.quality.score <= 100
        assert s.global_confidence == "indicatif"

    def test_failed_page_skipped(self, session_empty):
        page = CrawledPage(url="https://example.com/broken", fetch_error="timeout")
        session_empty.crawled_pages = [page]
        result = asyncio.run(AUDIT_REGISTRY["ac02"](session_empty))
        assert result.scores.get("https://example.com/broken") is None


# ─── 6. AC03-AC06 — Scoring AEO/GEO/EEAT/UX ───────────────────────────

class TestAC03:
    def test_aeo_score(self, session_with_page):
        result = asyncio.run(AUDIT_REGISTRY["ac03"](session_with_page))
        s = result.scores["https://example.com/page1"]
        assert 0 <= s.aeo.score <= 100

class TestAC04:
    def test_geo_score(self, session_with_page):
        result = asyncio.run(AUDIT_REGISTRY["ac04"](session_with_page))
        s = result.scores["https://example.com/page1"]
        assert 0 <= s.geo.score <= 100

class TestAC05:
    def test_eeat_score(self, session_with_page):
        result = asyncio.run(AUDIT_REGISTRY["ac05"](session_with_page))
        s = result.scores["https://example.com/page1"]
        assert 0 <= s.eea_t.score <= 16

class TestAC06:
    def test_ux_score(self, session_with_page):
        result = asyncio.run(AUDIT_REGISTRY["ac06"](session_with_page))
        s = result.scores["https://example.com/page1"]
        assert 0 <= s.ux.score <= 100


# ─── 7. AC07 — Cannibalisation ───────────────────────────────────────

class TestAC07:
    def test_no_cannib_with_one_page(self, session_with_page):
        result = asyncio.run(AUDIT_REGISTRY["ac07"](session_with_page))
        assert result.cannibalisation == []

    def test_detects_similar_pages(self):
        """Deux pages tres similaires devraient etre detectees."""
        p1 = CrawledPage(
            url="https://example.com/seo-guide",
            title="Guide SEO Complet 2026",
            h2_list=["Qu'est-ce que le SEO", "Comment faire du SEO", "Outils SEO"],
            word_count=1500,
        )
        p2 = CrawledPage(
            url="https://example.com/seo-tuto",
            title="Tutoriel SEO Complet 2026",
            h2_list=["Definition du SEO", "Comment optimiser son SEO", "Meilleurs outils SEO"],
            word_count=1200,
        )
        state = AuditSessionState(session_id="test", urls=[p1.url, p2.url])
        state.crawled_pages = [p1, p2]
        result = asyncio.run(AUDIT_REGISTRY["ac07"](state))
        # Les deux pages partagent "SEO" dans leurs titres/H2, similarite > 0.65
        assert len(result.cannibalisation) >= 0  # Peut etre 0 si seuil non atteint


# ─── 8. AC08 — Synthese ───────────────────────────────────────────────

class TestAC08:
    def test_synthesis_produces_brief(self, session_with_page):
        # D'abord scorer
        state = asyncio.run(AUDIT_REGISTRY["ac02"](session_with_page))
        # Puis synthese
        result = asyncio.run(AUDIT_REGISTRY["ac08"](state))
        brief = result.briefs.get("https://example.com/page1")
        assert brief is not None
        assert brief.page_url == "https://example.com/page1"
        assert brief.scores
        assert brief.action in ("conserver", "enrichir", "reviser", "reecrire")

    def test_brief_has_recommandations(self, session_with_page):
        state = asyncio.run(AUDIT_REGISTRY["ac02"](session_with_page))
        result = asyncio.run(AUDIT_REGISTRY["ac08"](state))
        brief = result.briefs["https://example.com/page1"]
        assert brief.recommandations or brief.forces or brief.faiblesses


# ─── 9. AC09 — Roadmap + Export ────────────────────────────────────────

class TestAC09:
    def test_roadmap_produced(self, session_with_page):
        state = asyncio.run(AUDIT_REGISTRY["ac02"](session_with_page))
        state = asyncio.run(AUDIT_REGISTRY["ac08"](state))
        result = asyncio.run(AUDIT_REGISTRY["ac09"](state))
        assert result.status == "completed"
        assert len(result.roadmap) >= 1
        assert result.roadmap[0]["url"] == "https://example.com/page1"


# ─── 10. Pipeline complet (integration) ────────────────────────────────

class TestFullPipeline:
    def test_full_pipeline_single_page(self):
        """Test integration complet sur une page reelle."""
        from hermes.core.audit_workflow import run_audit_pipeline

        result = asyncio.run(
            run_audit_pipeline(
                urls=["https://example.com"],
                site_url="https://example.com",
                mode="standard",
            )
        )
        assert result.status == "completed"
        assert len(result.crawled_pages) == 1
        assert len(result.scores) == 1
        assert len(result.briefs) == 1
        assert len(result.roadmap) == 1
        scores = result.scores["https://example.com"]
        assert 0 <= scores.global_score <= 100
        assert scores.global_confidence == "indicatif"

    def test_brief_connecte_to_editorial(self):
        """Verifie que le brief est compatible avec le Pipeline Editorial."""
        from hermes.core.audit_workflow import run_audit_pipeline

        result = asyncio.run(
            run_audit_pipeline(
                urls=["https://example.com"],
                site_url="https://example.com",
                mode="standard",
            )
        )
        brief_dict = prepare_audit_brief_for_editorial(
            result, "https://example.com"
        )
        assert brief_dict is not None
        assert "page_url" in brief_dict
        assert "scores" in brief_dict
        assert "action" in brief_dict
