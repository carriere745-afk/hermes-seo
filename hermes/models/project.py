"""Modeles Pydantic pour la couche Projet — Hermes SEO v3.

Centralise l'etat de chaque site/projet client :
- Scores consolides (tous pipelines)
- Recommandations executable (avec routing automatique)
- Disclaimers juridiques (8 types)
- Execution log (mega-agent P7)
- Onboarding guidance (quel pipeline, dans quel ordre)
- Local SEO (Google Business Profile)
- Disaster recovery (penalite, desindexation)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _uid() -> str:
    return uuid4().hex[:12]


# ─── Enums ────────────────────────────────────────────────────────────

class ProjectStatus(str, Enum):
    NEW = "new"                # Projet cree, aucun pipeline execute
    ONBOARDING = "onboarding"  # Premier diagnostic en cours
    ACTIVE = "active"           # Pipelines regulierement executes
    STALE = "stale"             # Pas d'activite depuis 30 jours
    ARCHIVED = "archived"       # Projet termine/archive
    RECOVERY = "recovery"       # Mode urgence (penalite, chute)


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"
    REQUIRES_HUMAN = "requires_human"


class DisclaimerType(str, Enum):
    PERFORMANCE = "performance"
    DELAIS = "delais"
    DONNEES = "donnees"
    IA_GENERATED = "ia_generated"
    YMYL = "ymyl"
    CONCURRENCE = "concurrence"
    BUDGET = "budget"
    NON_SUBSTITUTION = "non_substitution"


class OnboardingStep(str, Enum):
    WELCOME = "welcome"
    SITE_CONFIG = "site_config"
    API_SETUP = "api_setup"
    FIRST_AUDIT = "first_audit"
    FIRST_STRATEGY = "first_strategy"
    FIRST_CONTENT = "first_content"
    MONITORING = "monitoring"
    COMPLETE = "complete"


class ExecutionCategory(str, Enum):
    GENERATE = "generate"    # Creer du contenu, schema, llms.txt, emails, disavow
    OPTIMIZE = "optimize"    # Enrichir pages, ameliorer maillage, ajuster ancres
    PUBLISH = "publish"      # Envoyer vers CMS, Google Disavow, IndexNow
    MONITOR = "monitor"      # Suivre impact, positions, ROI


class SiteProfile(str, Enum):
    BLOG = "blog"
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    LOCAL = "local"
    CORPORATE = "corporate"
    MEDIA = "media"


# ─── Disclaimers ──────────────────────────────────────────────────────

DISCLAIMERS = {
    DisclaimerType.PERFORMANCE: {
        "id": "perf",
        "titre": "Projections de performance",
        "texte": "Les estimations de trafic, de positions et de ROI sont des projections "
                 "basees sur des donnees historiques et des moyennes sectorielles. Elles ne "
                 "constituent pas une garantie de resultats. Les performances reelles dependent "
                 "de centaines de facteurs : concurrence, mises a jour Google, comportement "
                 "des utilisateurs, qualite d'execution, delais de crawl, etc.",
        "affichage": "avant_toute_projection",
        "severite": "info",
    },
    DisclaimerType.DELAIS: {
        "id": "delais",
        "titre": "Delais de resultat",
        "texte": "Les delais indiques (ex: '3-6 mois') sont des estimations basees sur des "
                 "projets comparables. Le referencement naturel est un processus progressif. "
                 "Google peut prendre plusieurs semaines a indexer un nouveau contenu, "
                 "et plusieurs mois a evaluer pleinement sa qualite et sa pertinence.",
        "affichage": "apres_roadmap",
        "severite": "info",
    },
    DisclaimerType.DONNEES: {
        "id": "donnees",
        "titre": "Sources des donnees",
        "texte": "Les donnees de volume de recherche, de positions, de backlinks et de trafic "
                 "proviennent d'APIs tierces (Google Search Console, DataForSEO, TalorData, "
                 "Keywords Everywhere, RankParse). Leur exactitude depend de ces fournisseurs "
                 "et peut differer d'autres outils (Ahrefs, Semrush). Les donnees GSC sont "
                 "les plus fiables car directement fournies par Google.",
        "affichage": "avant_audit",
        "severite": "info",
    },
    DisclaimerType.IA_GENERATED: {
        "id": "ia",
        "titre": "Contenu genere par intelligence artificielle",
        "texte": "Certaines analyses et recommandations sont generees par des modeles d'IA "
                 "(Claude Haiku, Claude Sonnet). Bien que ces modeles soient entranes sur "
                 "des corpus SEO specialises, leurs recommandations doivent etre validees "
                 "par un humain avant toute action engageant des ressources. Hermes SEO "
                 "ne remplace pas le jugement d'un professionnel du referencement.",
        "affichage": "avant_recommandation_llm",
        "severite": "warning",
    },
    DisclaimerType.YMYL: {
        "id": "ymyl",
        "titre": "Contenu sensible (YMYL — Your Money Your Life)",
        "texte": "Les contenus relatifs a la sante, la finance, le droit, la securite ou "
                 "tout sujet reglemente (YMYL) necessitent une relecture par un expert "
                 "qualifie du domaine concerne. Les recommandations d'Hermes SEO ne "
                 "tiennent pas compte des reglementations sectorielles specifiques. "
                 "La publication de contenu YMYL sans validation experte peut engager "
                 "votre responsabilite legale et professionnelle.",
        "affichage": "avant_publication_ymyl",
        "severite": "critical",
    },
    DisclaimerType.CONCURRENCE: {
        "id": "concurrence",
        "titre": "Analyses concurrentielles",
        "texte": "Les analyses concurrentielles sont basees sur les donnees disponibles "
                 "publiquement (positions SERP, backlinks visibles, contenus indexables). "
                 "Les strategies internes des concurrents, leurs budgets, leurs equipes "
                 "et leurs projets a venir ne sont pas accessibles. Les classifications "
                 "de paysage concurrentiel sont des estimations, pas des certitudes.",
        "affichage": "avant_analyse_concurrentielle",
        "severite": "info",
    },
    DisclaimerType.BUDGET: {
        "id": "budget",
        "titre": "Estimations budgetaires",
        "texte": "Les couts estimes (redaction, netlinking, prestations) sont indicatifs "
                 "et bases sur des tarifs moyens du marche. Les couts reels peuvent varier "
                 "selon les prestataires, la complexite du sujet, la langue, le niveau "
                 "d'expertise requis et la disponibilite des ressources.",
        "affichage": "avant_estimation_cout",
        "severite": "info",
    },
    DisclaimerType.NON_SUBSTITUTION: {
        "id": "non_substitution",
        "titre": "Outil d'aide a la decision",
        "texte": "Hermes SEO est un outil d'aide a la decision et d'automatisation. "
                 "Il ne remplace pas un consultant SEO professionnel ni une strategie "
                 "humaine. Les recommandations automatisees doivent etre evaluees dans "
                 "le contexte global de votre strategie digitale. FC Solutions decline "
                 "toute responsabilite quant aux decisions prises sur la seule base "
                 "des recommandations d'Hermes SEO.",
        "affichage": "pied_de_page_global",
        "severite": "warning",
    },
}


class Disclaimer(BaseModel):
    id: str = ""
    type: DisclaimerType = DisclaimerType.NON_SUBSTITUTION
    titre: str = ""
    texte: str = ""
    affichage: str = ""
    severite: str = "info"
    accepted: bool = False
    accepted_at: Optional[datetime] = None


# ─── Execution Action ─────────────────────────────────────────────────

class ExecutionAction(BaseModel):
    """Une action executable generee a partir d'une recommandation."""
    id: str = Field(default_factory=_uid)
    source_pipeline: str = ""
    source_agent: str = ""
    source_recommandation_id: str = ""
    category: str = "generate"
    action_type: str = ""
    description: str = ""
    status: str = "pending"
    priority: str = "P2"
    automation_score: int = 50
    conflicts_with: list[str] = Field(default_factory=list)

    # Cible
    target_url: str = ""
    target_page: str = ""
    page_to_optimize: str = ""

    # Contenu
    content_to_generate: str = ""
    file_to_create: str = ""
    file_content: str = ""
    email_template: str = ""
    params: dict = Field(default_factory=dict)

    # Snapshots (rollback)
    snapshot_before: dict = Field(default_factory=dict)
    snapshot_after: dict = Field(default_factory=dict)

    # Execution
    execution_cost: float = 0.0
    human_approval_required: bool = False
    human_approved_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    execution_result: str = ""
    execution_error: str = ""

    # Impact tracking (→ P8)
    confidence_before: int = 0
    confidence_after: int = 0
    predicted_impact: str = ""
    actual_impact: Optional[dict] = None
    impact_j7: dict = Field(default_factory=dict)
    impact_j30: dict = Field(default_factory=dict)
    impact_j60: dict = Field(default_factory=dict)
    impact_j90: dict = Field(default_factory=dict)
    correction_factor: dict = Field(default_factory=dict)
    warning: str = ""

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)


# ─── Recommandation consolidee (tous pipelines → P7) ─────────────────

class ConsolidatedRecommendation(BaseModel):
    """Recommandation unifiee, pretes a etre transformee en ExecutionAction."""
    id: str = Field(default_factory=_uid)
    source_pipelines: list[str] = Field(default_factory=list)
    source_agents: list[str] = Field(default_factory=list)
    sujet: str = ""
    description: str = ""
    action_concrete: str = ""  # Ce que l'utilisateur doit faire
    action_executable: str = ""  # Ce que P7 peut executer automatiquement
    priority: str = "P2"
    effort_estime: str = ""
    cout_estime: float = 0.0
    impact_estime: str = ""
    delai_estime: str = ""
    confidence_score: int = 0
    requires_human: bool = False
    human_reason: str = ""  # Pourquoi c'est bloque (YMYL, legal, complexite...)
    disclaimers: list[str] = Field(default_factory=list)  # IDs des disclaimers a afficher
    created_at: datetime = Field(default_factory=datetime.now)


# ─── Project — Le modele central ──────────────────────────────────────

class Project(BaseModel):
    """Un site web / client gere par Hermes SEO."""
    id: str = Field(default_factory=_uid)
    nom: str = ""
    site_url: str = ""
    domain: str = ""
    profile: str = "blog"  # SiteProfile
    secteur: str = "autre"
    competitors: list[str] = Field(default_factory=list)
    keywords_cibles: list[str] = Field(default_factory=list)
    budget_mensuel: float = 0.0
    valeur_lead: float = 100.0
    taux_conversion: float = 0.02

    # Execution config
    max_actions_per_day: int = 20
    actions_executed_today: int = 0
    mode_execution: str = "semi-auto"  # auto, semi-auto, manual
    rollback_enabled: bool = True
    human_approval_threshold: int = 60

    # Meta
    status: str = "new"  # ProjectStatus
    onboarding_step: str = "welcome"
    onboarding_progress: int = 0  # 0-100%
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Pipelines — dernier run + scores
    pipelines: dict[str, dict] = Field(default_factory=lambda: {
        "p1": {"last_run": None, "status": "pending", "articles_generees": 0},
        "p2": {"last_run": None, "status": "pending", "pages_auditees": 0},
        "p3": {"last_run": None, "status": "pending", "issues_detectees": 0},
        "p4": {"last_run": None, "status": "pending", "keywords_trackes": 0},
        "p5": {"last_run": None, "status": "pending", "recommandations": 0},
        "p6": {"last_run": None, "status": "pending", "backlinks_audites": 0},
    })

    # Scores consolides
    health_score: int = 0          # Score global 0-100
    content_score: int = 0         # P1 + P2
    technique_score: int = 0       # P3
    visibility_score: int = 0      # P4
    strategy_score: int = 0        # P5
    authority_score: int = 0       # P6

    # Recommandations consolidees (alimentees par tous les pipelines)
    recommandations: list[ConsolidatedRecommendation] = Field(default_factory=list)

    # Actions en attente / executees (P7)
    execution_actions: list[ExecutionAction] = Field(default_factory=list)

    # Disclaimers acceptes
    disclaimers_accepted: dict[str, datetime] = Field(default_factory=dict)

    # Next action recommande
    next_action: str = ""
    next_pipeline: str = ""
    next_action_priority: str = "P2"

    # Local SEO (specifique)
    local_seo: dict = Field(default_factory=lambda: {
        "google_business_profile": "",
        "nap_consistency": {"nom": "", "adresse": "", "telephone": ""},
        "google_maps_url": "",
        "avis_count": 0,
        "avis_score": 0.0,
        "categories_gbp": [],
        "horaires": {},
    })

    # Flags
    ymyl_detected: bool = False
    penalite_suspectee: bool = False
    core_update_impacted: bool = False

    # Version
    version: str = "3.0"


# ─── Onboarding Wizard ────────────────────────────────────────────────

ONBOARDING_STEPS: list[dict] = [
    {
        "step": "welcome",
        "titre": "Bienvenue dans Hermes SEO",
        "description": "Configurons votre projet pour obtenir les meilleures recommandations.",
        "action": "Renseigner le nom du projet et l'URL du site",
        "pipeline": None,
        "disclaimers": ["non_substitution"],
    },
    {
        "step": "site_config",
        "titre": "Configuration du site",
        "description": "Definissez votre profil, votre secteur et vos concurrents principaux.",
        "action": "Selectionner le profil et le secteur",
        "pipeline": None,
        "disclaimers": [],
    },
    {
        "step": "api_setup",
        "titre": "Connectez vos APIs",
        "description": "GSC est gratuit et indispensable. DataForSEO debloque les backlinks et les volumes.",
        "action": "Connecter au moins GSC",
        "pipeline": None,
        "disclaimers": ["donnees"],
    },
    {
        "step": "first_audit",
        "titre": "Premier diagnostic",
        "description": "Lancons un audit technique et de contenu pour evaluer votre situation.",
        "action": "Lancer P3 (Audit Technique) puis P2 (Audit de Contenu)",
        "pipeline": "p3",
        "disclaimers": ["donnees"],
        "recommended_order": ["p3", "p2"],
    },
    {
        "step": "first_strategy",
        "titre": "Definissons votre strategie",
        "description": "Avec les donnees d'audit, nous pouvons batir une roadmap sur mesure.",
        "action": "Lancer P4 (SERP) puis P5 (Strategie)",
        "pipeline": "p5",
        "disclaimers": ["performance", "delais", "budget"],
        "recommended_order": ["p4", "p5"],
    },
    {
        "step": "first_content",
        "titre": "Produisons du contenu",
        "description": "Votre roadmap est prete. Creons vos premiers contenus optimises.",
        "action": "Generer un article pilier (P1) et auditer vos backlinks (P6)",
        "pipeline": "p1",
        "disclaimers": ["ia_generated", "ymyl", "delais"],
        "recommended_order": ["p1", "p6"],
    },
    {
        "step": "monitoring",
        "titre": "Surveillance continue",
        "description": "Vos contenus sont en ligne. Surveillons leurs performances.",
        "action": "Activer le suivi cron P4 (quotidien/hebdomadaire)",
        "pipeline": "p4",
        "disclaimers": ["performance", "delais"],
    },
    {
        "step": "complete",
        "titre": "Projet operationnel",
        "description": "Hermes SEO surveille, alerte et recommande. Consultez votre dashboard chaque semaine.",
        "action": "Programmer un check mensuel + revue de strategie",
        "pipeline": None,
        "disclaimers": [],
    },
]

# Reconnaissance automatique du profil selon l'URL
PROFILE_DETECTION: dict[str, list[str]] = {
    "ecommerce": ["boutique", "shop", "store", "produit", "achat", "panier", "ecommerce", "catalogue"],
    "saas": ["app", "software", "demo", "pricing", "tarif", "login", "dashboard", "api"],
    "local": ["tours", "paris", "lyon", "marseille", "bordeaux", "nantes", "lille", "strasbourg",
              "nettoyage", "plombier", "electricien", "coiffeur", "boulanger", "restaurant"],
    "corporate": ["solutions", "services", "expertise", "groupe", "holding", "institutionnel"],
    "media": ["actu", "news", "blog", "magazine", "journal", "media", "podcast"],
}
