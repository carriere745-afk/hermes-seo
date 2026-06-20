"""Regles de scoring adaptatives par type de page.

Portage depuis saas-seo/lib/page-type-rules.js (545 lignes).
Chaque type de page a des dimensions Required/Valued/Neutral/Penalty
avec des ponderations et plages de mots differentes.

Source unique : ce fichier. Tous les agents de scoring s'y referent.
"""

from enum import Enum
from typing import Optional


class ScoreWeight(str, Enum):
    REQUIRED = "required"    # Absence = -points
    VALUED = "valued"         # Present = +points
    NEUTRAL = "neutral"       # Ni bonus ni malus
    PENALTY = "penalty"       # Present = -points (ex: keyword stuffing)


class PageTypeProfile:
    """Profil de scoring pour un type de page donne."""

    def __init__(
        self,
        type_name: str,
        min_words: int = 300,
        max_words: int = 5000,
        optimal_words: int = 1500,
        dimensions: Optional[dict[str, tuple[ScoreWeight, float]]] = None,
        ymyl_strict: bool = False,
        requires_author: bool = False,
        requires_sources: bool = False,
    ):
        self.type_name = type_name
        self.min_words = min_words
        self.max_words = max_words
        self.optimal_words = optimal_words
        self.dimensions = dimensions or {}
        self.ymyl_strict = ymyl_strict
        self.requires_author = requires_author
        self.requires_sources = requires_sources

    def get_weight(self, dimension: str) -> tuple[ScoreWeight, float]:
        """Retourne (type_de_poids, multiplicateur) pour une dimension."""
        return self.dimensions.get(
            dimension,
            (ScoreWeight.VALUED, 1.0),  # Default: bonus normal
        )


# ─── Profils par type de page ──────────────────────────────────────────

PROFILES: dict[str, PageTypeProfile] = {
    "article": PageTypeProfile(
        type_name="article",
        min_words=600,
        optimal_words=1200,
        max_words=3000,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 1.0),
            "densite_semantique": (ScoreWeight.VALUED, 1.0),
            "reponse_paa": (ScoreWeight.VALUED, 0.8),
            "originalite": (ScoreWeight.VALUED, 1.2),
            "fraicheur": (ScoreWeight.VALUED, 1.0),
            "respect_aeo": (ScoreWeight.VALUED, 1.0),
            "respect_geo": (ScoreWeight.VALUED, 0.8),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.0),
            "naturalite": (ScoreWeight.VALUED, 1.0),
        },
    ),
    "pilier": PageTypeProfile(
        type_name="pilier",
        min_words=2000,
        optimal_words=4000,
        max_words=10000,
        requires_sources=True,
        requires_author=True,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 0.8),
            "densite_semantique": (ScoreWeight.VALUED, 1.2),
            "reponse_paa": (ScoreWeight.REQUIRED, 1.0),
            "originalite": (ScoreWeight.REQUIRED, 1.2),
            "fraicheur": (ScoreWeight.VALUED, 1.0),
            "respect_aeo": (ScoreWeight.REQUIRED, 1.2),
            "respect_geo": (ScoreWeight.REQUIRED, 1.2),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.5),
            "naturalite": (ScoreWeight.VALUED, 0.8),
        },
    ),
    "service_local": PageTypeProfile(
        type_name="service_local",
        min_words=800,
        optimal_words=1500,
        max_words=3000,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 1.0),
            "densite_semantique": (ScoreWeight.NEUTRAL, 0.0),
            "reponse_paa": (ScoreWeight.NEUTRAL, 0.0),
            "originalite": (ScoreWeight.VALUED, 0.8),
            "fraicheur": (ScoreWeight.NEUTRAL, 0.0),
            "respect_aeo": (ScoreWeight.NEUTRAL, 0.0),
            "respect_geo": (ScoreWeight.NEUTRAL, 0.0),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.2),
            "naturalite": (ScoreWeight.VALUED, 1.0),
        },
    ),
    "comparatif": PageTypeProfile(
        type_name="comparatif",
        min_words=1500,
        optimal_words=2500,
        max_words=5000,
        requires_sources=True,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 0.8),
            "densite_semantique": (ScoreWeight.VALUED, 1.0),
            "reponse_paa": (ScoreWeight.VALUED, 0.8),
            "originalite": (ScoreWeight.REQUIRED, 1.5),
            "fraicheur": (ScoreWeight.VALUED, 1.0),
            "respect_aeo": (ScoreWeight.NEUTRAL, 0.0),
            "respect_geo": (ScoreWeight.VALUED, 1.0),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.2),
            "naturalite": (ScoreWeight.VALUED, 1.0),
        },
    ),
    "landing": PageTypeProfile(
        type_name="landing",
        min_words=400,
        optimal_words=800,
        max_words=2000,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 1.0),
            "densite_semantique": (ScoreWeight.NEUTRAL, 0.0),
            "reponse_paa": (ScoreWeight.NEUTRAL, 0.0),
            "originalite": (ScoreWeight.VALUED, 1.0),
            "fraicheur": (ScoreWeight.NEUTRAL, 0.0),
            "respect_aeo": (ScoreWeight.NEUTRAL, 0.0),
            "respect_geo": (ScoreWeight.NEUTRAL, 0.0),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.5),
            "naturalite": (ScoreWeight.VALUED, 1.2),
        },
    ),
    "fiche_produit": PageTypeProfile(
        type_name="fiche_produit",
        min_words=400,
        optimal_words=800,
        max_words=2000,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 0.8),
            "densite_semantique": (ScoreWeight.NEUTRAL, 0.0),
            "reponse_paa": (ScoreWeight.NEUTRAL, 0.0),
            "originalite": (ScoreWeight.VALUED, 0.8),
            "fraicheur": (ScoreWeight.VALUED, 1.0),
            "respect_aeo": (ScoreWeight.NEUTRAL, 0.0),
            "respect_geo": (ScoreWeight.NEUTRAL, 0.0),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.5),
            "naturalite": (ScoreWeight.VALUED, 1.0),
        },
    ),
    "faq": PageTypeProfile(
        type_name="faq",
        min_words=400,
        optimal_words=800,
        max_words=2000,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 1.0),
            "densite_semantique": (ScoreWeight.NEUTRAL, 0.0),
            "reponse_paa": (ScoreWeight.VALUED, 0.8),
            "originalite": (ScoreWeight.NEUTRAL, 0.0),
            "fraicheur": (ScoreWeight.VALUED, 1.0),
            "respect_aeo": (ScoreWeight.VALUED, 1.2),
            "respect_geo": (ScoreWeight.NEUTRAL, 0.0),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.0),
            "naturalite": (ScoreWeight.VALUED, 1.0),
        },
    ),
    "news": PageTypeProfile(
        type_name="news",
        min_words=400,
        optimal_words=700,
        max_words=1500,
        requires_sources=True,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 1.0),
            "densite_semantique": (ScoreWeight.NEUTRAL, 0.0),
            "reponse_paa": (ScoreWeight.NEUTRAL, 0.0),
            "originalite": (ScoreWeight.VALUED, 0.5),
            "fraicheur": (ScoreWeight.REQUIRED, 2.0),
            "respect_aeo": (ScoreWeight.NEUTRAL, 0.0),
            "respect_geo": (ScoreWeight.NEUTRAL, 0.0),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.5),
            "naturalite": (ScoreWeight.VALUED, 1.0),
        },
    ),
    "glossaire": PageTypeProfile(
        type_name="glossaire",
        min_words=200,
        optimal_words=500,
        max_words=1000,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 1.0),
            "densite_semantique": (ScoreWeight.NEUTRAL, 0.0),
            "reponse_paa": (ScoreWeight.NEUTRAL, 0.0),
            "originalite": (ScoreWeight.NEUTRAL, 0.0),
            "fraicheur": (ScoreWeight.NEUTRAL, 0.0),
            "respect_aeo": (ScoreWeight.NEUTRAL, 0.0),
            "respect_geo": (ScoreWeight.NEUTRAL, 0.0),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.0),
            "naturalite": (ScoreWeight.VALUED, 1.0),
        },
    ),
    "temoignage": PageTypeProfile(
        type_name="temoignage",
        min_words=400,
        optimal_words=800,
        max_words=1500,
        requires_author=False,
        requires_sources=False,
        dimensions={
            "lisibilite": (ScoreWeight.VALUED, 1.2),
            "densite_semantique": (ScoreWeight.NEUTRAL, 0.0),
            "reponse_paa": (ScoreWeight.NEUTRAL, 0.0),
            "originalite": (ScoreWeight.REQUIRED, 1.5),
            "fraicheur": (ScoreWeight.NEUTRAL, 0.0),
            "respect_aeo": (ScoreWeight.NEUTRAL, 0.0),
            "respect_geo": (ScoreWeight.NEUTRAL, 0.0),
            "absence_erreurs": (ScoreWeight.REQUIRED, 1.0),
            "naturalite": (ScoreWeight.REQUIRED, 1.5),
        },
    ),
}


def get_profile(type_page: str) -> PageTypeProfile:
    """Retourne le profil de scoring pour un type de page."""
    return PROFILES.get(type_page, PROFILES["article"])


def get_word_range(type_page: str) -> tuple[int, int, int]:
    """Retourne (min, optimal, max) en mots pour un type de page."""
    profile = get_profile(type_page)
    return (profile.min_words, profile.optimal_words, profile.max_words)


def is_ymyl(topic: str) -> bool:
    """Detecte si un sujet est YMYL (Your Money Your Life)."""
    ymyl_keywords = {
        "assurance", "credit", "pret", "cancer", "traitement", "diagnostic",
        "avocat", "juridique", "fiscal", "impot", "comptable", "investissement",
        "placement", "retraite", "mutuelle", "hospitalisation", "chirurgie",
        "medicament", "vaccin", "contraception", "divorce", "heritage",
        "licenciement", "banqueroute", "faillite", "syndic", "copropriete",
    }
    return any(kw in topic.lower() for kw in ymyl_keywords)


def should_require_author(type_page: str, topic: str = "") -> bool:
    """Determine si un auteur identifie est requis."""
    profile = get_profile(type_page)
    if profile.requires_author:
        return True
    if is_ymyl(topic):
        return True
    return False
