"""Modeles Pydantic pour le Pipeline 6 — Maillage & Backlinks.

18 agents (B00-B17). Audit backlinks, CRM campagnes, scoring autorite,
prospect discovery, anchor strategy, portfolio optimizer, entity authority.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _uid() -> str:
    return uuid4().hex[:12]


# ─── Enums ────────────────────────────────────────────────────────────

class BacklinkPhase(str, Enum):
    STARTUP = "startup"
    COLLECTE = "collecte"
    ANALYSE = "analyse"
    SYNTHESE = "synthese"
    EXECUTION = "execution"
    EXPORT = "export"


class LinkType(str, Enum):
    GUEST_POST = "guest_post"
    LINK_INSERTION = "link_insertion"
    ARTICLE_SPONSORISE = "article_sponsorise"
    ANNUAIRE = "annuaire"
    PARTENARIAT = "partenariat"
    TRIBUNE = "tribune"
    COMMUNIQUE = "communique"
    INTERVIEW = "interview"
    PODCAST = "podcast"
    FORUM = "forum"
    MENTION = "mention"
    BROKEN_LINK = "broken_link"
    LINKABLE = "linkable"
    EARNING_LINK = "earning_link"
    AUTRE = "autre"


class CampaignStatus(str, Enum):
    PROSPECT = "prospect"
    CONTACTE = "contacte"
    RELANCE = "relance"
    EN_COURS = "en_cours"
    ACCEPTE = "accepte"
    PUBLIE = "publie"
    REFUSE = "refuse"
    ABANDONNE = "abandonne"


class ToxicityLevel(str, Enum):
    SAFE = "safe"
    LOW_RISK = "low_risk"
    SUSPICIOUS = "suspicious"
    TOXIC = "toxic"


class AnchorType(str, Enum):
    EXACT_MATCH = "exact_match"
    PARTIAL_MATCH = "partial_match"
    BRAND = "brand"
    URL_NAKED = "url_naked"
    GENERIC = "generic"
    IMAGE = "image"
    LONG_TAIL = "long_tail"


class EntityType(str, Enum):
    PERSON = "person"
    BRAND = "brand"
    ORGANIZATION = "organization"
    PRODUCT = "product"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class PrioriteAction(str, Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


# ─── Domaines & Backlinks ─────────────────────────────────────────────

class ReferringDomain(BaseModel):
    id: str = Field(default_factory=_uid)
    domain: str = ""
    domain_rating: float = 0.0  # 0-100
    topical_score: float = 0.0  # 0-100 pertinence thematique
    link_scarcity: float = 0.0  # 0-100 rarete des liens sortants
    geo_relevance: float = 0.0  # 0-100 pertinence geographique
    backlinks_count: int = 0
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    domain_type: str = "blog"  # media_national, media_sectoriel, blog, annuaire, forum, etc.
    country: str = ""
    language: str = "fr"
    is_competitor: bool = False
    trust_flow: float = 0.0
    citation_flow: float = 0.0


class Backlink(BaseModel):
    id: str = Field(default_factory=_uid)
    source_url: str = ""
    source_domain: str = ""
    target_url: str = ""
    anchor_text: str = ""
    anchor_type: str = "generic"
    link_type: str = "editorial"  # editorial, annuaire, forum, etc.
    is_dofollow: bool = True
    is_lost: bool = False
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    source_dr: float = 0.0
    source_traffic: int = 0
    source_keywords_count: int = 0
    toxicity_score: float = 0.0
    toxicity_level: str = "safe"
    confidence: str = "medium"


class BacklinkOpportunity(BaseModel):
    id: str = Field(default_factory=_uid)
    domain: str = ""
    url: str = ""
    contact_email: str = ""
    contact_name: str = ""
    domain_rating: float = 0.0
    topical_score: float = 0.0
    opportunity_type: str = "guest_post"  # guest_post, link_insertion, mention, broken_link, annuaire
    priority: str = "P2"
    impact_score: float = 0.0  # 0-100
    feasibility_score: float = 0.0
    cost_estime: float = 0.0
    effort_estime: str = "2h"
    roi_estime: float = 0.0
    status: str = "prospect"
    source: str = ""  # B04 gap, B05 mention, B12 prospect discovery
    description: str = ""
    keywords_cibles: list[str] = Field(default_factory=list)


# ─── Campagnes & Contacts ─────────────────────────────────────────────

class CampaignContact(BaseModel):
    id: str = Field(default_factory=_uid)
    opportunity_id: str = ""
    domain: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_role: str = ""
    status: str = "prospect"  # CampaignStatus
    last_contact_date: Optional[datetime] = None
    next_followup_date: Optional[datetime] = None
    followup_count: int = 0
    notes: str = ""
    email_thread_id: str = ""
    cost_engaged: float = 0.0
    link_acquired: bool = False
    acquired_date: Optional[datetime] = None
    acquired_url: str = ""
    relationship_score: float = 0.0  # 0-100 B17


class CampaignResult(BaseModel):
    id: str = Field(default_factory=_uid)
    campaign_id: str = ""
    backlink_id: str = ""
    acquisition_date: Optional[datetime] = None
    cost: float = 0.0
    link_type: str = ""
    target_page: str = ""
    position_at_acquisition: float = 0.0
    traffic_at_acquisition: float = 0.0
    ranking_change_j30: float = 0.0
    ranking_change_j60: float = 0.0
    ranking_change_j90: float = 0.0
    traffic_change_j30: float = 0.0
    traffic_change_j60: float = 0.0
    traffic_change_j90: float = 0.0
    confidence_score: float = 0.0


# ─── Entity & Media ───────────────────────────────────────────────────

class EntityMention(BaseModel):
    id: str = Field(default_factory=_uid)
    entity_name: str = ""
    entity_type: str = "brand"
    source_url: str = ""
    source_authority: float = 0.0
    context: str = ""
    sentiment: str = "neutral"
    has_link: bool = False
    detected_at: datetime = Field(default_factory=datetime.now)


class MediaRelationship(BaseModel):
    id: str = Field(default_factory=_uid)
    media_domain: str = ""
    contact_email: str = ""
    contact_name: str = ""
    total_contacts: int = 0
    total_responses: int = 0
    total_publications: int = 0
    avg_response_time_days: float = 0.0
    relationship_score: float = 0.0  # 0-100
    last_contact: Optional[datetime] = None


class PortfolioSnapshot(BaseModel):
    id: str = Field(default_factory=_uid)
    media_national_ratio: float = 0.0
    media_sectoriel_ratio: float = 0.0
    blogs_experts_ratio: float = 0.0
    annuaires_ratio: float = 0.0
    associations_ratio: float = 0.0
    partenariats_ratio: float = 0.0
    podcasts_ratio: float = 0.0
    communautes_ratio: float = 0.0
    target_mix: dict = Field(default_factory=dict)
    captured_at: datetime = Field(default_factory=datetime.now)


# ─── Recommandation backlinks ─────────────────────────────────────────

class BacklinkRecommandation(BaseModel):
    id: str = Field(default_factory=_uid)
    domaine_cible: str = ""
    url_cible: str = ""
    type_action: str = "guest_post"
    priorite: str = "P2"
    justification: str = ""
    cout_estime: float = 0.0
    effort_estime: str = ""
    impact_estime: str = ""
    delai_estime: str = "2-4 semaines"
    keywords_cibles: list[str] = Field(default_factory=list)
    confidence_score: int = 0
    opportunity_id: str = ""


# ─── Etat de session Backlinks ────────────────────────────────────────

class BacklinksState(BaseModel):
    session_id: str = Field(default_factory=_uid)
    site_url: str = ""
    domain: str = ""
    mode: str = "standard"
    profile: str = "blog"  # blog, ecommerce, saas, local, corporate, agressif, defensif

    # Configuration
    competitors: list[str] = Field(default_factory=list)
    keywords_cibles: list[str] = Field(default_factory=list)
    budget_mensuel: float = 500.0

    # Phase 0
    startup_ok: bool = False
    apis_disponibles: dict[str, bool] = Field(default_factory=dict)

    # Phase 1 — Collecte
    backlinks: list[Backlink] = Field(default_factory=list)
    referring_domains: list[ReferringDomain] = Field(default_factory=list)

    # Phase 2 — Analyse
    quality_scores: dict[str, float] = Field(default_factory=dict)  # domain → quality score
    toxic_domains: list[dict] = Field(default_factory=list)
    competitor_gaps: list[dict] = Field(default_factory=list)
    link_reclamations: list[dict] = Field(default_factory=list)
    prospect_discoveries: list[dict] = Field(default_factory=list)
    anchor_profile: dict = Field(default_factory=dict)  # actuel vs cible
    portfolio_snapshot: Optional[PortfolioSnapshot] = None
    entity_mentions: list[dict] = Field(default_factory=list)
    media_relationships: list[dict] = Field(default_factory=list)
    scarcity_scores: dict[str, float] = Field(default_factory=dict)
    authority_graph: dict = Field(default_factory=dict)

    # Phase 3 — Synthese
    recommandations: list[BacklinkRecommandation] = Field(default_factory=list)

    # Phase 4 — Execution
    opportunities: list[BacklinkOpportunity] = Field(default_factory=list)
    campaigns: list[CampaignContact] = Field(default_factory=list)
    campaign_results: list[CampaignResult] = Field(default_factory=list)

    # Phase 5 — Export
    rapport_html: str = ""
    rapport_json: str = ""
    pipelines_to_trigger: list[dict] = Field(default_factory=list)

    # AI / GEO Status (B16)
    ai_status: dict = Field(default_factory=dict)

    # Scores globaux
    authority_score: int = 0
    link_profile_health: int = 0
    anchor_risk_score: int = 0
    competitor_gap_score: int = 0
    portfolio_diversity_score: int = 0

    # Session
    status: str = "created"
    phase: str = "startup"
    current_agent: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    errors: list[str] = Field(default_factory=list)
    version: str = "3.0"
