"""Types partagés par tous les modèles Hermes SEO."""

from datetime import datetime
from enum import Enum
from uuid import uuid4


class SessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class QualityMode(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"
    COMPLIANCE = "compliance"
    DEBUG = "debug"


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED_AUTO = "skipped_auto"
    SKIPPED_USER = "skipped_user"
    FAILED = "failed"
    BLOCKED = "blocked"
    REQUIRES_REVIEW = "requires_review"


class Intention(str, Enum):
    INFORMATIVE = "informative"
    TRANSACTIONNELLE = "transactionnelle"
    COMPARATIVE = "comparative"
    LOCALE = "locale"
    NAVIGATIONNELLE = "navigationnelle"


class TypePage(str, Enum):
    ARTICLE = "article"
    PILIER = "pilier"
    FICHE_PRODUIT = "fiche_produit"
    FAQ = "faq"
    SERVICE_LOCAL = "service_local"
    COMPARATIF = "comparatif"
    LANDING = "landing"
    NEWS = "news"
    GLOSSAIRE = "glossaire"
    TEMOIGNAGE = "temoignage"


class Secteur(str, Enum):
    DROIT = "droit"
    FINANCE = "finance"
    SANTE = "sante"
    RH = "rh"
    DONNEES_PERSONNELLES = "donnees_personnelles"
    CYBERSECURITE = "cybersecurite"
    ENFANTS = "enfants"
    VEHICULES = "vehicules"
    PRODUITS_REGLEMENTES = "produits_reglementes"
    ECOMMERCE = "ecommerce"
    SAAS = "saas"
    FORMATION = "formation"
    IMMOBILIER = "immobilier"
    TOURISME = "tourisme"
    AUTRE = "autre"


SECTEURS_REGLEMENTES: set[str] = {
    Secteur.DROIT.value,
    Secteur.FINANCE.value,
    Secteur.SANTE.value,
    Secteur.RH.value,
    Secteur.DONNEES_PERSONNELLES.value,
    Secteur.CYBERSECURITE.value,
    Secteur.ENFANTS.value,
    Secteur.VEHICULES.value,
    Secteur.PRODUITS_REGLEMENTES.value,
}


def generate_session_id() -> str:
    return uuid4().hex[:12]
