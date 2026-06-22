"""Modeles Pydantic pour le Pipeline Audit de Contenu.

14 signaux extraits par page + scores + recommandations.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Extraction ────────────────────────────────────────────────────────

class CrawledPage(BaseModel):
    """Page crawlee avec 55+ signaux extraits."""
    url: str
    status_code: int = 200
    final_url: str = ""  # Apres redirects
    fetch_error: str = ""

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
    word_count_visible: int = 0
    text_html_ratio: float = 0.0
    language_detected: str = ""

    # Images
    images_total: int = 0
    images_with_alt: int = 0
    images_lazy: int = 0
    images_with_dimensions: int = 0

    # Liens
    internal_links: int = 0
    external_links: int = 0
    broken_links: int = 0
    internal_links_list: list[dict] = Field(default_factory=list)

    # Schema
    json_ld_types: list[str] = Field(default_factory=list)
    json_ld_valid: bool = False
    microdata_present: bool = False

    # UX
    has_cta: bool = False
    cta_count: int = 0
    has_breadcrumbs: bool = False
    has_video: bool = False
    reading_time_minutes: int = 0

    # Technique
    content_type: str = ""
    charset: str = "utf-8"
    has_viewport: bool = False
    is_amp: bool = False
    redirect_chain: list[str] = Field(default_factory=list)

    # Auteur
    author_detected: bool = False
    author_name: str = ""
    date_published: str = ""
    date_modified: str = ""

    # Indexabilite (checks de base)
    is_indexable: bool = True
    has_noindex: bool = False
    robots_blocked: bool = False

    # SERP context (ajoute par AC01b)
    serp_context: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict:
        return self.model_dump()


# ─── Scoring ────────────────────────────────────────────────────────────

class DimensionScore(BaseModel):
    """Score pour une dimension (0-100) avec details."""
    score: int = 0
    max_score: int = 100
    issues: list[dict] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class AuditScores(BaseModel):
    """Scores agregees pour une page."""
    seo_onpage: DimensionScore = Field(default_factory=DimensionScore)
    quality: DimensionScore = Field(default_factory=DimensionScore)
    aeo: DimensionScore = Field(default_factory=DimensionScore)
    geo: DimensionScore = Field(default_factory=DimensionScore)
    eea_t: DimensionScore = Field(default_factory=DimensionScore)
    ux: DimensionScore = Field(default_factory=DimensionScore)
    transparency: DimensionScore = Field(default_factory=DimensionScore)
    global_score: int = 0
    global_confidence: str = "indicatif"


# ─── Recommandations ────────────────────────────────────────────────────

class AuditRecommendation(BaseModel):
    """Une recommandation actionnable."""
    action: str = ""  # "ajouter_faq", "ajouter_sources", etc.
    description: str = ""
    impact: dict[str, float] = Field(default_factory=dict)  # {"aeo": 25, "global": 12}
    effort_estime: str = ""
    priorite: int = 1  # 1=critique, 2=elevee, 3=moyenne, 4=faible


class AuditBrief(BaseModel):
    """Brief d'audit consomme par le Pipeline Editorial."""
    mode_audit: bool = True
    page_url: str = ""
    current_content: str = ""
    scores: dict[str, int] = Field(default_factory=dict)
    forces: list[str] = Field(default_factory=list)
    faiblesses: list[str] = Field(default_factory=list)
    recommandations: list[AuditRecommendation] = Field(default_factory=list)
    cannibalisation: dict = Field(default_factory=dict)
    action: str = "conserver"
    priorite: int = 3
    template_suggere: str = "article"
    sections_to_keep: list[str] = Field(default_factory=list)
    sections_to_remove: list[str] = Field(default_factory=list)
    sources_to_add: list[str] = Field(default_factory=list)
    internal_links_to_add: list[str] = Field(default_factory=list)
    human_review_required: bool = False


class AuditSessionState(BaseModel):
    """Etat complet d'une session d'audit."""
    session_id: str = ""
    site_url: str = ""
    mode: str = "standard"
    urls: list[str] = Field(default_factory=list)
    crawled_pages: list[CrawledPage] = Field(default_factory=list)
    scores: dict[str, AuditScores] = Field(default_factory=dict)
    briefs: dict[str, AuditBrief] = Field(default_factory=dict)
    cannibalisation: list[dict] = Field(default_factory=list)
    roadmap: list[dict] = Field(default_factory=list)
    status: str = "created"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    error_count: int = 0
    current_agent: str = ""
