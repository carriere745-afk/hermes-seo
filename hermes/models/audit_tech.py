"""Modeles Pydantic pour le Pipeline Audit Technique.

20 agents (T00-T20), 5 phases. Chaque constat a un score de confiance
(High/Medium/Low), une source de preuve, et des recommandations adaptees au CMS.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ─── Page crawlee (technique) ────────────────────────────────────────

class TechCrawlPage(BaseModel):
    """Page crawlee avec signaux techniques."""
    url: str
    status_code: int = 200
    final_url: str = ""
    fetch_error: str = ""

    # HTTP
    http_headers: dict[str, str] = Field(default_factory=dict)
    content_type: str = ""
    charset: str = "utf-8"
    content_length_bytes: int = 0
    load_time_ms: int = 0
    is_https: bool = True
    redirect_chain: list[str] = Field(default_factory=list)
    redirect_count: int = 0

    # Meta
    title: str = ""
    title_length: int = 0
    meta_description: str = ""
    meta_description_length: int = 0
    canonical: str = ""
    robots_meta: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    twitter_card: str = ""

    # Structure Hn
    h1: str = ""
    h1_count: int = 0
    h2_list: list[str] = Field(default_factory=list)
    h3_list: list[str] = Field(default_factory=list)
    heading_hierarchy_ok: bool = True

    # Contenu
    word_count: int = 0
    text_html_ratio: float = 0.0
    language_detected: str = ""

    # Images
    images_total: int = 0
    images_without_alt: int = 0

    # Liens
    internal_links_count: int = 0
    external_links_count: int = 0
    internal_links_list: list[dict] = Field(default_factory=list)

    # Schema
    json_ld_types: list[str] = Field(default_factory=list)
    json_ld_valid: bool = False
    microdata_present: bool = False

    # Hreflang
    hreflang_tags: list[dict] = Field(default_factory=list)

    # UX
    has_viewport: bool = False
    has_cta: bool = False
    has_breadcrumbs: bool = False
    has_video: bool = False

    # Indexabilite
    is_indexable: bool = True
    has_noindex: bool = False
    robots_blocked: bool = False

    # CMS
    cms_detected: str = ""
    cms_version: str = ""
    cms_confidence: int = 0

    # Maillage
    internal_incoming: int = 0
    crawl_depth: int = 0

    # Performance
    page_size_kb: float = 0.0
    ttfb_ms: int = 0

    def to_dict(self) -> dict:
        return self.model_dump()


# ─── Constat technique ────────────────────────────────────────────────

class TechIssue(BaseModel):
    """Un probleme technique detecte avec confiance, preuve et recommandation."""
    id: str = ""  # "P-001"
    category: str = ""  # "architecture", "performance", "securite", "indexation"...
    description: str = ""
    url: str = ""
    observed: str = ""  # Donnee observee (ex: "title de 65 caracteres")
    rule: str = ""  # Regle declenchee (ex: "title > 60 caracteres")
    confidence: Literal["high", "medium", "low"] = "medium"
    source_agent: str = ""  # "T05", "T07"...
    severity: Literal["critical", "high", "medium", "low", "info"] = "medium"
    impact_business: Literal["High", "Medium", "Low"] = "Low"
    gain_potentiel: Literal["High", "Medium", "Low"] = "Low"
    effort: str = ""  # "5 min", "2h"...
    priority: Literal["P0", "P1", "P2", "P3"] = "P3"
    do_not_recommend_if: list[str] = Field(default_factory=list)
    cms_location: Optional[str] = None  # "WordPress → Yoast → Title"
    evidence: Optional[dict[str, Any]] = None


# ─── Score par dimension ──────────────────────────────────────────────

class TechDimensionScore(BaseModel):
    """Score 0-100 pour une dimension technique."""
    score: int = 0
    max_score: int = 100
    confidence: Literal["high", "medium", "low"] = "medium"
    issues_count: int = 0
    critical_count: int = 0
    details: list[str] = Field(default_factory=list)


# ─── Scores agreges ────────────────────────────────────────────────────

class TechAuditScores(BaseModel):
    """Scores techniques globaux."""
    crawlability: TechDimensionScore = Field(default_factory=TechDimensionScore)
    indexation: TechDimensionScore = Field(default_factory=TechDimensionScore)
    architecture: TechDimensionScore = Field(default_factory=TechDimensionScore)
    structure: TechDimensionScore = Field(default_factory=TechDimensionScore)
    content: TechDimensionScore = Field(default_factory=TechDimensionScore)
    performance: TechDimensionScore = Field(default_factory=TechDimensionScore)
    mobile: TechDimensionScore = Field(default_factory=TechDimensionScore)
    structured_data: TechDimensionScore = Field(default_factory=TechDimensionScore)
    international: TechDimensionScore = Field(default_factory=TechDimensionScore)
    security: TechDimensionScore = Field(default_factory=TechDimensionScore)
    maillage: TechDimensionScore = Field(default_factory=TechDimensionScore)
    global_score: int = 0
    global_confidence: Literal["high", "medium", "low"] = "medium"


# ─── Etat de session ──────────────────────────────────────────────────

class TechAuditState(BaseModel):
    """Etat complet d'une session d'audit technique."""
    session_id: str = ""
    site_url: str = ""
    domain: str = ""
    mode: str = "standard"  # fast/standard/premium/debug
    consent_given: bool = False
    profile: str = "blog"  # ecommerce/blog/institutionnel/agence/saas

    # Entree
    urls: list[str] = Field(default_factory=list)
    max_urls: int = 100
    max_depth: int = 3
    respect_robots_txt: bool = True
    rate_limit_rps: float = 2.0

    # Collecte
    crawled_pages: list[TechCrawlPage] = Field(default_factory=list)
    sitemap_urls: list[str] = Field(default_factory=list)
    robots_txt: str = ""
    cms_detected: str = ""
    cms_version: str = ""
    cms_confidence: int = 0

    # Analyse
    graph_edges: list[dict] = Field(default_factory=list)  # liens internes
    silos: list[dict] = Field(default_factory=list)
    silos_fantomes: list[dict] = Field(default_factory=list)
    orphans: list[str] = Field(default_factory=list)
    duplicates: list[dict] = Field(default_factory=list)

    # Issues
    issues: list[TechIssue] = Field(default_factory=list)
    critical_issues: list[TechIssue] = Field(default_factory=list)

    # Scores
    scores: TechAuditScores = Field(default_factory=TechAuditScores)

    # Synthese
    roadmap: list[dict] = Field(default_factory=list)
    business_impact_summary: dict[str, int] = Field(default_factory=dict)
    pipelines_to_trigger: list[dict[str, Any]] = Field(default_factory=list)

    # Session
    status: str = "created"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    error_count: int = 0
    current_agent: str = ""
    version: str = "2.0"
