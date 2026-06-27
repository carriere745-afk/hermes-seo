"""Modeles Pydantic pour le Pipeline 4 — SERP & Visibility Intelligence.

11 agents (S00-S10). Mode continu (cron quotidien) + on-demand.
Historique SQLite pour positions, alertes, correlactions.
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# ─── Entree de position ────────────────────────────────────────────────

class PositionEntry(BaseModel):
    """Une entree dans l'historique des positions."""
    url: str
    keyword: str
    position: int
    position_previous: int = 0
    variation: int = 0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    search_volume: int = 0
    device: str = "mobile"
    source: str = "GSC"  # GSC / DataForSEO / openserp
    date: datetime = Field(default_factory=datetime.now)
    url_classee: str = ""  # URL effectivement classee (peut differer de l'url attendue)
    featured_snippet: bool = False


# ─── Alerte ────────────────────────────────────────────────────────────

class AlertEntry(BaseModel):
    """Une alerte generee par S07."""
    type: str  # chute_critique, desindexation, core_update, concurrent_depasse, gain_top10...
    keyword: str = ""
    url: str = ""
    valeur_avant: Optional[float] = None
    valeur_apres: Optional[float] = None
    priorite: str = "P2"  # P0, P1, P2, info
    canal: str = "UI"  # UI / Email / Webhook
    statut: str = "ouvert"  # ouvert / traite / ignore
    date: datetime = Field(default_factory=datetime.now)
    note: str = ""


# ─── Entree concurrent ─────────────────────────────────────────────────

class CompetitorEntry(BaseModel):
    """Position d'un concurrent sur un mot-cle."""
    domain: str
    keyword: str
    position: int
    url: str = ""
    date: datetime = Field(default_factory=datetime.now)
    source: str = "DataForSEO"


# ─── Share of Voice ────────────────────────────────────────────────────

class ShareOfVoiceEntry(BaseModel):
    """Part de voix d'un domaine a une date donnee."""
    domain: str
    date: datetime
    sov_impressions: float = 0.0  # 0-100%
    sov_clicks: float = 0.0
    weighted_visibility: float = 0.0
    evolution_7d: float = 0.0
    evolution_30d: float = 0.0


# ─── SERP Feature ─────────────────────────────────────────────────────

class SerpFeatureEntry(BaseModel):
    """Fonctionnalite SERP pour un mot-cle."""
    keyword: str
    feature_type: str  # featured_snippet, paa, ai_overview, pack_local, video_carousel...
    present: bool = False
    url_site: str = ""
    opportunity_score: int = 0  # 0-100
    date: datetime = Field(default_factory=datetime.now)


# ─── AI Visibility ─────────────────────────────────────────────────────

class AIVisibilityEntry(BaseModel):
    """Citation du site par une IA generative."""
    keyword: str
    source_ia: str  # SGE / Perplexity / ChatGPT / Bing
    cited_url: str = ""
    citation_context: str = ""
    confidence: Literal["high", "medium", "low"] = "medium"
    date: datetime = Field(default_factory=datetime.now)


# ─── Action log ────────────────────────────────────────────────────────

class ActionEntry(BaseModel):
    """Action Hermes enregistree pour correlation."""
    type: str  # publication / correction / revision
    url: str
    pipeline_source: str  # P1 / P3 / P7
    date: datetime = Field(default_factory=datetime.now)
    details: str = ""


# ─── Correlation ──────────────────────────────────────────────────────

class CorrelationEntry(BaseModel):
    """Correlation entre une action et l'evolution des positions."""
    action_id: str
    url: str
    keyword: str
    delta_j7: int = 0
    delta_j30: int = 0
    delta_j60: int = 0
    delta_j90: int = 0
    confidence_score: Literal["High", "Medium", "Low"] = "Low"
    pattern: str = ""  # Ex: "enrichissement AEO → +3 positions en 14j"


# ─── Quick Win ─────────────────────────────────────────────────────────

class QuickWin(BaseModel):
    """Page en position 4-15 avec fort potentiel."""
    url: str
    keyword: str
    position: int
    search_volume: int = 0
    impressions_28j: int = 0
    ctr_actuel: float = 0.0
    business_score: float = 0.0
    trend: str = "stable"  # up / stable / down
    action_recommandee: str = ""
    pipeline_cible: str = ""  # P1 / P3 / P6
    priorite: str = "P1"


# ─── Etat de session ──────────────────────────────────────────────────

class SerpVisibilityState(BaseModel):
    """Etat complet d'une session Pipeline 4."""
    session_id: str = ""
    site_url: str = ""
    domain: str = ""
    mode: str = "standard"  # fast / standard / premium / debug

    # Configuration
    keywords: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    alert_thresholds: dict[str, int] = Field(default_factory=dict)
    tracking_devices: list[str] = Field(default_factory=lambda: ["mobile"])
    cron_schedule: str = "daily"

    # Collecte
    positions: list[PositionEntry] = Field(default_factory=list)
    competitor_positions: list[CompetitorEntry] = Field(default_factory=list)
    serp_features: list[SerpFeatureEntry] = Field(default_factory=list)
    ai_visibility: list[AIVisibilityEntry] = Field(default_factory=list)

    # Analyse
    variations: list[dict] = Field(default_factory=list)
    quick_wins: list[QuickWin] = Field(default_factory=list)
    share_of_voice: list[ShareOfVoiceEntry] = Field(default_factory=list)
    content_gaps: list[dict] = Field(default_factory=list)

    # Decisions
    alerts: list[AlertEntry] = Field(default_factory=list)
    core_update_detected: bool = False
    core_update_date: Optional[datetime] = None

    # Correlation
    actions_log: list[ActionEntry] = Field(default_factory=list)
    correlations: list[CorrelationEntry] = Field(default_factory=list)

    # Scores
    health_score: int = 0
    ai_visibility_score: int = 0
    sov_score: int = 0

    # Synthese
    rapport_html: str = ""
    benchmark: dict = Field(default_factory=dict)  # SV12 competitive benchmark
    resume_executif: list[str] = Field(default_factory=list)
    pipelines_to_trigger: list[dict[str, Any]] = Field(default_factory=list)

    # Session
    status: str = "created"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    current_agent: str = ""
    cycle_count: int = 0
    version: str = "3.0"
