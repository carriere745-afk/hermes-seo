"""Modèles Pydantic Hermes SEO — contrats de données entre agents."""

from hermes.models.agent_data import (
    AeoBlocks, AntiCannibData, Brouillon, ConformiteData,
    DifferenciationData, EeatScore, ErreurFactuelle, ExportData,
    ExternalLink, ExternalLinks, FactCheckData, FeedbackData,
    FicheEntreprise, FichePersona, GeoData, GrilleScores,
    ImagePlan, ImageSpec, IntentTypeData, InternalLink,
    InternalLinks, LocalisedData, MultiformatData, OffreConversion,
    RefreshPlan, SchemaData, ScoresFinaux, Section, SeoData,
    SerpData, SerpResult, SupervisorVerdict, TemplateData,
    VariantAB, VariantsAB,
)
from hermes.models.common import (
    AgentStatus, Intention, QualityMode, Secteur,
    SECTEURS_REGLEMENTES, SessionStatus, TypePage,
    generate_session_id,
)
from hermes.models.session import (
    AgentResult, SessionConfig, SessionState,
)
from hermes.models.strategie import (
    ActionType, AgentMode, DecisionTrace, ExecutiveSummary,
    ForecastEntry, GapConcurrentiel, HermesEvent, KillListEntry,
    PortfolioCategory, PredictionEntry, PrioriteAction,
    Recommandation, SeverityLevel, StrategiePhase, StrategieState, Sujet,
)
from hermes.models.backlinks import (
    AnchorType, Backlink, BacklinkOpportunity, BacklinkPhase,
    BacklinkRecommandation, BacklinksState, CampaignContact,
    CampaignResult, CampaignStatus, EntityMention, EntityType,
    LinkType, MediaRelationship, PortfolioSnapshot, PrioriteAction as BlPrioriteAction,
    ReferringDomain, Sentiment, ToxicityLevel,
)
from hermes.models.project import (
    ConsolidatedRecommendation, Disclaimer, DisclaimerType,
    ExecutionAction, ExecutionCategory, ExecutionStatus,
    OnboardingStep, Project, ProjectStatus, SiteProfile,
    DISCLAIMERS, ONBOARDING_STEPS, PROFILE_DETECTION,
)

__all__ = [
    # Common
    "AgentStatus",
    "SessionStatus",
    "QualityMode",
    "Intention",
    "TypePage",
    "Secteur",
    "SECTEURS_REGLEMENTES",
    "generate_session_id",
    # Session
    "AgentResult",
    "SessionConfig",
    "SessionState",
    # Agent 00
    "SupervisorVerdict",
    # Agent 01
    "FicheEntreprise",
    # Agent 02
    "FichePersona",
    # Agent 03
    "SerpData",
    "SerpResult",
    # Agent 04
    "IntentTypeData",
    # Agent 05
    "OffreConversion",
    # Agent 06
    "DifferenciationData",
    # Agent 07
    "Section",
    "TemplateData",
    # Agent 08
    "AntiCannibData",
    # Agent 09
    "Brouillon",
    # Agent 10
    "SeoData",
    # Agent 11
    "AeoBlocks",
    # Agent 12
    "GeoData",
    # Agent 13
    "EeatScore",
    # Agent 14
    "ConformiteData",
    # Agent 15
    "ErreurFactuelle",
    "FactCheckData",
    # Agent 16
    "InternalLink",
    "InternalLinks",
    # Agent 17
    "ExternalLink",
    "ExternalLinks",
    # Agent 18
    "MultiformatData",
    # Agent 19
    "VariantAB",
    "VariantsAB",
    # Agent 20
    "LocalisedData",
    # Agent 21
    "SchemaData",
    # Agent 22
    "ImagePlan",
    "ImageSpec",
    # Agent 23
    "ExportData",
    # Agent 24
    "RefreshPlan",
    # Agent 25
    "GrilleScores",
    "ScoresFinaux",
    # Agent 26
    "FeedbackData",
    # Pipeline 5 — Strategie
    "ActionType", "AgentMode", "DecisionTrace", "ExecutiveSummary",
    "ForecastEntry", "GapConcurrentiel", "HermesEvent", "KillListEntry",
    "PortfolioCategory", "PredictionEntry", "PrioriteAction",
    "Recommandation", "SeverityLevel", "StrategiePhase", "StrategieState", "Sujet",
    # Pipeline 6 — Backlinks
    "AnchorType", "Backlink", "BacklinkOpportunity", "BacklinkPhase",
    "BacklinkRecommandation", "BacklinksState", "CampaignContact",
    "CampaignResult", "CampaignStatus", "EntityMention", "EntityType",
    "LinkType", "MediaRelationship", "PortfolioSnapshot",
    "ReferringDomain", "Sentiment", "ToxicityLevel",
    # Pipeline 7/8 — Project & Execution
    "ConsolidatedRecommendation", "Disclaimer", "DisclaimerType",
    "ExecutionAction", "ExecutionCategory", "ExecutionStatus",
    "OnboardingStep", "Project", "ProjectStatus", "SiteProfile",
]
