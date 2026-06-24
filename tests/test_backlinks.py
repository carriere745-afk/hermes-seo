"""Tests unitaires Pipeline 6 — Maillage & Backlinks."""

import pytest

from hermes.models.backlinks import (
    BacklinksState, Backlink, ReferringDomain, BacklinkRecommandation,
    CampaignContact, BacklinkOpportunity, PortfolioSnapshot, EntityMention,
    MediaRelationship, CampaignResult,
)
from hermes.agents.backlinks import BACKLINKS_REGISTRY, BACKLINKS_ORDER


@pytest.fixture
def base_state():
    return BacklinksState(
        site_url="https://example.com",
        domain="example.com",
        mode="standard",
        profile="blog",
        competitors=["concurrent1.fr", "concurrent2.fr"],
        keywords_cibles=["seo", "referencement", "netlinking"],
        budget_mensuel=500.0,
    )


# ─── Tests B00-B01 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_b00_startup(base_state):
    state = base_state
    state.session_id = ""
    result = await BACKLINKS_REGISTRY["b00"](state)
    assert result.startup_ok is True
    assert result.session_id.startswith("bl-example.com")
    assert result.status == "running"


@pytest.mark.asyncio
async def test_b01_import(base_state):
    state = base_state
    state.startup_ok = True
    state.apis_disponibles = {"dataforseo": False, "gsc": False, "bing": False, "indexnow": True}
    result = await BACKLINKS_REGISTRY["b01"](state)
    assert len(result.backlinks) > 0
    assert len(result.referring_domains) > 0


# ─── Tests B02-B03 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_b02_scoring(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="blog-expert.fr", domain_rating=72, domain_type="blog", backlinks_count=3),
        ReferringDomain(domain="media-pro.fr", domain_rating=65, domain_type="media_sectoriel", backlinks_count=1),
        ReferringDomain(domain="annuaire.xyz", domain_rating=15, domain_type="annuaire", backlinks_count=10),
    ]
    state.backlinks = [
        Backlink(source_domain="blog-expert.fr", anchor_text="example.com", source_dr=72),
        Backlink(source_domain="blog-expert.fr", anchor_text="visiter le site", source_dr=72),
        Backlink(source_domain="media-pro.fr", anchor_text="exemple de seo", source_dr=65),
        Backlink(source_domain="annuaire.xyz", anchor_text="example.com avis", source_dr=15),
    ]
    result = await BACKLINKS_REGISTRY["b02"](state)
    assert len(result.quality_scores) == 3
    assert result.anchor_profile.get("current")
    assert result.anchor_profile.get("total_anchors") == 4


@pytest.mark.asyncio
async def test_b03_toxiques(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="pbn-spam.xyz", domain_rating=5, domain_type="blog", backlinks_count=20),
        ReferringDomain(domain="blog-expert.fr", domain_rating=72, domain_type="blog", backlinks_count=2),
    ]
    state.backlinks = [
        Backlink(source_domain="pbn-spam.xyz", anchor_text="acheter seo pas cher", source_dr=5,
                anchor_type="exact_match"),
        Backlink(source_domain="pbn-spam.xyz", anchor_text="meilleur referencement", source_dr=5,
                anchor_type="exact_match"),
        Backlink(source_domain="blog-expert.fr", anchor_text="example.com", source_dr=72,
                anchor_type="brand"),
    ]
    result = await BACKLINKS_REGISTRY["b03"](state)
    assert len(result.toxic_domains) >= 1
    assert result.anchor_risk_score >= 0


# ─── Tests B04-B05-B12 ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_b04_gap(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="blog-expert.fr", domain_rating=72, domain_type="blog"),
    ]
    result = await BACKLINKS_REGISTRY["b04"](state)
    assert isinstance(result.competitor_gaps, list)
    assert result.competitor_gap_score >= 0


@pytest.mark.asyncio
async def test_b05_reclamation(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="blog-expert.fr", domain_rating=72, domain_type="blog"),
    ]
    state.backlinks = [
        Backlink(source_domain="old-site.fr", target_url="https://example.com/", is_lost=True,
                anchor_text="example", source_dr=30),
    ]
    result = await BACKLINKS_REGISTRY["b05"](state)
    assert len(result.link_reclamations) > 0


@pytest.mark.asyncio
async def test_b12_prospect_discovery(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="blog-expert.fr", domain_rating=72, domain_type="blog"),
    ]
    result = await BACKLINKS_REGISTRY["b12"](state)
    assert len(result.prospect_discoveries) > 0


# ─── Tests B14-B06 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_b14_anchor_strategy(base_state):
    state = base_state
    state.startup_ok = True
    state.anchor_profile = {
        "current": {"brand": 30, "exact_match": 25, "generic": 20, "partial_match": 10, "url_naked": 10, "long_tail": 5},
        "total_anchors": 20,
        "unique_anchors": 8,
    }
    state.referring_domains = [
        ReferringDomain(domain="blog-expert.fr", domain_rating=72, domain_type="blog"),
    ]
    result = await BACKLINKS_REGISTRY["b14"](state)
    assert "deviations" in result.anchor_profile
    assert "health_score" in result.anchor_profile


@pytest.mark.asyncio
async def test_b06_recommandations(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="blog-expert.fr", domain_rating=72, domain_type="blog"),
    ]
    state.competitor_gaps = [
        {"domain": "gap-domain.fr", "concurrent": "concurrent1.fr", "domain_rating": 68, "score_gap": 75, "topical_score": 80},
    ]
    state.prospect_discoveries = [
        {"domain": "media-pro.fr", "domain_type": "media_sectoriel", "domain_rating": 65, "topical_score": 70, "relevance_score": 67, "opportunity_type": "guest_post"},
    ]
    state.link_reclamations = [
        {"type": "lost_link", "source_domain": "old-blog.fr", "raison": "Lien perdu a reclamer", "score": 70, "source_url": "https://old-blog.fr/page"},
    ]
    state.anchor_profile = {"alerts": ["Trop d'ancres exact match"]}
    result = await BACKLINKS_REGISTRY["b06"](state)
    assert len(result.recommandations) > 0


# ─── Tests B07-B11 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_b07_crm(base_state):
    state = base_state
    state.startup_ok = True
    result = await BACKLINKS_REGISTRY["b07"](state)
    assert isinstance(result.campaigns, list)


@pytest.mark.asyncio
async def test_b11_export(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="blog-expert.fr", domain_rating=72, domain_type="blog", backlinks_count=3),
        ReferringDomain(domain="media-pro.fr", domain_rating=65, domain_type="media_sectoriel", backlinks_count=1),
    ]
    state.backlinks = [
        Backlink(source_domain="blog-expert.fr", anchor_text="example.com", source_dr=72,
                anchor_type="brand", link_type="editorial"),
    ]
    state.recommandations = [
        BacklinkRecommandation(domaine_cible="blog-expert.fr", type_action="guest_post", priorite="P1",
                              cout_estime=150, justification="Test", confidence_score=75),
    ]
    state.toxic_domains = [
        {"domain": "spam.xyz", "toxicity_level": "toxic", "reasons": ["TLD suspect"], "recommandation": "Desavouer"},
    ]
    state.anchor_profile = {"deviations": {}}
    result = await BACKLINKS_REGISTRY["b11"](state)
    assert result.authority_score >= 0
    assert result.link_profile_health >= 0
    assert len(result.rapport_html) > 0
    assert result.status == "completed"


# ─── Tests V1.5-V3 agents ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_b05b_broken_links(base_state):
    state = base_state
    state.startup_ok = True
    result = await BACKLINKS_REGISTRY["b05b"](state)
    assert result.current_agent == "b05b"


@pytest.mark.asyncio
async def test_b08_moteur_preuve(base_state):
    state = base_state
    state.startup_ok = True
    result = await BACKLINKS_REGISTRY["b08"](state)
    assert result.current_agent == "b08"


@pytest.mark.asyncio
async def test_b09_scarcity(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="rare-blog.fr", domain_rating=60, backlinks_count=1),
    ]
    result = await BACKLINKS_REGISTRY["b09"](state)
    assert len(result.scarcity_scores) == 1


@pytest.mark.asyncio
async def test_b10_authority_graph(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="hub.fr", domain_rating=85, domain_type="media_national"),
    ]
    result = await BACKLINKS_REGISTRY["b10"](state)
    assert "hubs" in result.authority_graph


@pytest.mark.asyncio
async def test_b15_portfolio(base_state):
    state = base_state
    state.startup_ok = True
    state.referring_domains = [
        ReferringDomain(domain="media.fr", domain_rating=85, domain_type="media_national"),
        ReferringDomain(domain="blog.fr", domain_rating=50, domain_type="blog"),
    ]
    result = await BACKLINKS_REGISTRY["b15"](state)
    assert result.portfolio_snapshot is not None


@pytest.mark.asyncio
async def test_b16_entity_authority(base_state):
    state = base_state
    state.startup_ok = True
    result = await BACKLINKS_REGISTRY["b16"](state)
    assert len(result.entity_mentions) > 0


@pytest.mark.asyncio
async def test_b17_media_relationship(base_state):
    state = base_state
    state.startup_ok = True
    state.campaigns = [
        CampaignContact(domain="blog-expert.fr", status="publie", link_acquired=True,
                       followup_count=2, contact_email="test@test.fr"),
    ]
    result = await BACKLINKS_REGISTRY["b17"](state)
    assert len(result.media_relationships) > 0


# ─── Tests Modeles ─────────────────────────────────────────────────────

def test_backlink_model():
    bl = Backlink(source_url="https://blog.fr/article", source_domain="blog.fr",
                 target_url="https://example.com/", anchor_text="example",
                 anchor_type="brand", source_dr=72)
    assert bl.id
    assert bl.source_domain == "blog.fr"
    assert bl.is_dofollow is True


def test_backlinks_state_serialization(base_state):
    js = base_state.model_dump_json()
    assert "example.com" in js
    restored = BacklinksState.model_validate_json(js)
    assert restored.domain == "example.com"


def test_recommandation_model():
    rec = BacklinkRecommandation(
        domaine_cible="blog-expert.fr", type_action="guest_post",
        priorite="P1", cout_estime=150, confidence_score=75,
    )
    assert rec.id
    assert rec.priorite == "P1"


def test_campaign_contact_model():
    c = CampaignContact(domain="blog-expert.fr", status="prospect",
                       contact_email="test@test.fr")
    assert c.id
    assert c.status == "prospect"


def test_portfolio_snapshot_model():
    ps = PortfolioSnapshot(
        media_national_ratio=20, media_sectoriel_ratio=25,
        blogs_experts_ratio=15, annuaires_ratio=10,
        associations_ratio=10, partenariats_ratio=10,
        podcasts_ratio=5, communautes_ratio=5,
    )
    assert ps.media_national_ratio == 20


def test_entity_mention_model():
    em = EntityMention(entity_name="example", entity_type="brand",
                      source_url="https://blog.fr", sentiment="positive")
    assert em.entity_name == "example"


# ─── Tests Pipeline Complet ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_full_pipeline_standard(base_state):
    state = base_state
    state.mode = "standard"
    for agent_id in BACKLINKS_ORDER:
        if agent_id in BACKLINKS_REGISTRY:
            state = await BACKLINKS_REGISTRY[agent_id](state)
    assert state.status == "completed"
    assert state.authority_score >= 0
    assert len(state.rapport_html) > 0


@pytest.mark.asyncio
async def test_full_pipeline_fast(base_state):
    state = base_state
    state.mode = "fast"
    for agent_id in BACKLINKS_ORDER:
        if agent_id in BACKLINKS_REGISTRY:
            state = await BACKLINKS_REGISTRY[agent_id](state)
    assert state.status == "completed"


@pytest.mark.asyncio
async def test_db_integration():
    from hermes.core.backlinks_db import init_db, get_db_stats
    init_db()
    stats = get_db_stats()
    assert "backlinks" in stats
    assert "campaigns" in stats
