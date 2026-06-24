"""Modeles Pydantic pour le Pipeline 5 — Strategie Editoriale.

18 agents (ST00-ST11). Analyse business, roadmap, forecast, kill list.
Confidence Score + Decision Trace sur chaque recommandation.
Observability Layer : hermes_events + predictions_history.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _uid() -> str:
    return uuid4().hex[:12]


# ─── Enums ────────────────────────────────────────────────────────────

class StrategiePhase(str, Enum):
    STARTUP = "startup"
    ANALYSE = "analyse"
    SYNTHESE = "synthese"
    EXPORT = "export"


class AgentMode(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"
    COMPLIANCE = "compliance"


class PrioriteAction(str, Enum):
    P0 = "P0"  # Critique / immédiat
    P1 = "P1"  # Haute / 1-3 mois
    P2 = "P2"  # Moyenne / 3-6 mois
    P3 = "P3"  # Basse / 6-12 mois
    KILL = "KILL"  # À ne pas faire


class PortfolioCategory(str, Enum):
    ACQUISITION = "acquisition"
    RETENTION = "retention"
    DEFENSE = "defense"
    CONVERSION = "conversion"
    AUTHORITY = "authority"


class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActionType(str, Enum):
    CREER_PILIER = "creer_pilier"
    CREER_SATELLITE = "creer_satellite"
    ENRICHIR_EXISTANT = "enrichir_existant"
    FUSIONNER = "fusionner"
    SEPARER = "separer"
    SUPPRIMER = "supprimer"
    OPTIMISER = "optimiser"
    DEFENDRE = "defendre"
    CONSOLIDER = "consolider"
    CREER_FAQ = "creer_faq"
    ENRICHIR_FAQ = "enrichir_faq"
    CREER_COMPARATIF = "creer_comparatif"


# ─── Decision Trace ───────────────────────────────────────────────────

class DecisionTrace(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    rules_applied: list[str] = Field(default_factory=list)
    calcul: str = ""
    decision: str = ""


# ─── Sujet (Topic) ────────────────────────────────────────────────────

class Sujet(BaseModel):
    id: str = Field(default_factory=_uid)
    nom: str = ""
    keywords: list[str] = Field(default_factory=list)
    volume_total: int = 0
    volume_principal: int = 0
    intention: str = "informative"
    type_page: str = "article"
    silo: str = "general"
    couvert: bool = False
    page_existante: str = ""
    topical_authority: int = 0  # 0-100
    position_moyenne: float = 0.0
    concurrents_top5: list[str] = Field(default_factory=list)
    opportunite_score: int = 0  # 0-100
    feasibility_score: int = 0  # ST04b
    business_score: float = 0.0  # ST05
    geo_opportunity: int = 0  # ST04c, 0-100
    effort_estime: str = ""
    cout_estime: float = 0.0
    roi_12mois: float = 0.0
    delai_resultats: str = ""


# ─── Recommandation ───────────────────────────────────────────────────

class Recommandation(BaseModel):
    id: str = Field(default_factory=_uid)
    sujet: str = ""
    action: str = "creer_pilier"
    priorite: str = "P2"
    justification: str = ""
    keywords: list[str] = Field(default_factory=list)
    volume_recherche: int = 0
    effort_estime: str = ""
    cout_estime: float = 0.0
    trafic_estime: int = 0
    leads_estimes: int = 0
    roi_12mois: float = 0.0
    delai_resultats: str = "3-6 mois"
    pipeline_cible: str = "P1"
    portfolio: str = "acquisition"
    dependencies: list[str] = Field(default_factory=list)
    confidence_score: int = 0  # 0-100
    confidence_justification: str = ""
    trace: Optional[DecisionTrace] = None


# ─── Kill List Entry ─────────────────────────────────────────────────

class KillListEntry(BaseModel):
    id: str = Field(default_factory=_uid)
    sujet: str = ""
    raison: str = ""
    categorie: str = ""  # cannibalisation, hors_scope, faible_potentiel, ymyl, duplicate
    severite: str = "medium"
    keywords: list[str] = Field(default_factory=list)
    page_concernee: str = ""
    justification: str = ""
    trace: Optional[DecisionTrace] = None


# ─── Gap Concurrentiel ────────────────────────────────────────────────

class GapConcurrentiel(BaseModel):
    id: str = Field(default_factory=_uid)
    domaine: str = ""
    keyword: str = ""
    notre_position: float = 0.0
    leur_position: float = 0.0
    contenu_manquant: str = ""
    opportunite: str = ""
    score_gap: int = 0


# ─── Forecast Entry ───────────────────────────────────────────────────

class ForecastEntry(BaseModel):
    mois: int = 0
    trafic_estime: int = 0
    leads_estimes: int = 0
    revenu_estime: float = 0.0
    cout_estime: float = 0.0
    cumul_roi: float = 0.0


# ─── Executive Summary ────────────────────────────────────────────────

class ExecutiveSummary(BaseModel):
    sante_strategique: int = 0  # 0-100
    top_opportunites: list[dict] = Field(default_factory=list)  # max 3
    top_menaces: list[dict] = Field(default_factory=list)  # max 2
    roi_12mois_bas: float = 0.0
    roi_12mois_haut: float = 0.0
    budget_mensuel_recommande: float = 0.0
    horizon_roadmap: str = "12 mois"
    perte_estimee_si_inaction: str = ""
    recommandations_cles: list[str] = Field(default_factory=list)


# ─── Etat de session Strategie ────────────────────────────────────────

class StrategieState(BaseModel):
    session_id: str = Field(default_factory=_uid)
    site_url: str = ""
    domain: str = ""
    mode: str = "standard"
    profile: str = "blog"  # blog, ecommerce, saas, local, corporate
    secteur: str = "autre"

    # Configuration d'entree
    keywords_monitored: list[str] = Field(default_factory=list)
    competitors: list[str] = Field(default_factory=list)
    silos_config: list[str] = Field(default_factory=list)
    pages_existantes: list[dict] = Field(default_factory=list)
    budget_mensuel: float = 0.0
    valeur_lead: float = 100.0  # Valeur moyenne d'un lead en euros
    taux_conversion: float = 0.02  # 2% par defaut

    # Phase 0
    startup_ok: bool = False
    pipelines_disponibles: dict[str, bool] = Field(default_factory=dict)
    ga4_configure: bool = False

    # Phase 1 — Analyses
    sujets: list[Sujet] = Field(default_factory=list)
    topical_map: list[dict] = Field(default_factory=list)
    topical_authority_scores: dict[str, int] = Field(default_factory=dict)
    cannibalisations: list[dict] = Field(default_factory=list)
    opportunites: list[dict] = Field(default_factory=list)
    gaps_concurrentiels: list[GapConcurrentiel] = Field(default_factory=list)
    feasibility_scores: dict[str, int] = Field(default_factory=dict)
    geo_opportunities: list[dict] = Field(default_factory=list)
    business_scores: dict[str, float] = Field(default_factory=dict)
    seo_economics: list[dict] = Field(default_factory=list)
    silos_analysis: list[dict] = Field(default_factory=list)
    fusion_separation: list[dict] = Field(default_factory=list)

    # Phase 2 — Synthese
    recommandations: list[Recommandation] = Field(default_factory=list)
    forecast: list[ForecastEntry] = Field(default_factory=list)
    portfolio_allocation: dict[str, float] = Field(default_factory=dict)
    revue_humaine_flags: list[dict] = Field(default_factory=list)
    priorisation_config: dict[str, float] = Field(default_factory=dict)
    kill_list: list[KillListEntry] = Field(default_factory=list)

    # Phase 3 — Export
    executive_summary: Optional[ExecutiveSummary] = None
    rapport_html: str = ""
    rapport_json: str = ""
    pipelines_to_trigger: list[dict[str, Any]] = Field(default_factory=list)

    # Session
    status: str = "created"
    phase: str = "startup"
    current_agent: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    errors: list[str] = Field(default_factory=list)
    version: str = "3.0"


# ─── Hermes Event (Observability) ─────────────────────────────────────

class HermesEvent(BaseModel):
    event_id: str = Field(default_factory=_uid)
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: str = ""
    pipeline_id: str = "strategie"
    agent_id: str = ""
    model: str = "none"
    tokens_used: int = 0
    cost: float = 0.0
    duration_ms: int = 0
    success: bool = True
    error: str = ""
    predictions: Optional[dict] = None
    confidence: float = 0.0
    trace: Optional[dict] = None


# ─── Prediction Entry ─────────────────────────────────────────────────

class PredictionEntry(BaseModel):
    prediction_id: str = Field(default_factory=_uid)
    session_id: str = ""
    pipeline_id: str = "strategie"
    agent_id: str = ""
    action_type: str = ""
    url: str = ""
    keyword: str = ""
    predicted_traffic: int = 0
    predicted_leads: int = 0
    predicted_roi: float = 0.0
    confidence: float = 0.0
    date_prediction: datetime = Field(default_factory=datetime.now)
