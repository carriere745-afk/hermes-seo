"""Modèles Pydantic pour les sorties de chaque agent Hermes SEO.

Chaque modèle correspond au contrat de sortie d'un agent spécifique.
Toutes les données transitant entre agents doivent être validées par ces modèles.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


# ─── Agent 00 — Superviseur ───────────────────────────────────────────


class SupervisorVerdict(BaseModel):
    valid: bool
    blocked_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_agent_id: str = ""
    next_action: str = "proceed"  # proceed, block, retry, skip


# ─── Agent 01 — Brief Entreprise ──────────────────────────────────────


class FicheEntreprise(BaseModel):
    nom: str
    secteur: str
    positionnement: str
    offres: list[str] = Field(default_factory=list)
    ton_marque: str = ""
    preuves: list[str] = Field(default_factory=list)
    contraintes_legales: list[str] = Field(default_factory=list)
    mots_cles_interdits: list[str] = Field(default_factory=list)
    elements_differenciants: list[str] = Field(default_factory=list)
    url: Optional[str] = None


# ─── Agent 02 — Persona ───────────────────────────────────────────────


class FichePersona(BaseModel):
    nom_persona: str
    maturite: str  # debutant, intermediaire, expert
    vocabulaire_recommande: list[str] = Field(default_factory=list)
    canal_acquisition: str = ""  # search, social, email, direct
    objectif_lecture: str = ""
    freins: list[str] = Field(default_factory=list)
    questions_typiques: list[str] = Field(default_factory=list)
    niveau_expertise: str = "intermediaire"


# ─── Agent 03 — Analyse SERP ──────────────────────────────────────────


class SerpResult(BaseModel):
    position: int
    title: str
    url: str
    snippet: str
    domain: str = ""
    has_featured_snippet: bool = False
    has_paa: bool = False
    has_ai_overview: bool = False
    word_count: Optional[int] = None
    h2_count: Optional[int] = None
    image_count: Optional[int] = None


class SerpData(BaseModel):
    top10: list[SerpResult] = Field(default_factory=list)
    paa: list[str] = Field(default_factory=list)  # People Also Ask
    featured_snippets: list[dict[str, Any]] = Field(default_factory=list)
    ai_overviews: list[dict[str, Any]] = Field(default_factory=list)
    concurrents_directs: list[str] = Field(default_factory=list)
    mots_cles_associes: list[str] = Field(default_factory=list)
    search_volume: Optional[int] = None
    keyword_difficulty: Optional[int] = None
    total_results: Optional[int] = None
    snack_pack: list[dict[str, Any]] = Field(default_factory=list)


# ─── Agent 04 — Intention & Type ──────────────────────────────────────


class IntentTypeData(BaseModel):
    intention: str  # informative, transactionnelle, comparative, locale
    type_page: str  # article, pilier, fiche_produit, faq, etc.
    justification: str = ""
    serp_consensus: str = ""


# ─── Agent 05 — Offre & Conversion ────────────────────────────────────


class OffreConversion(BaseModel):
    benefices: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    preuves: list[str] = Field(default_factory=list)
    cta_principal: str = ""
    cta_secondaire: str = ""
    valeur_ajoutee_unique: str = ""


# ─── Agent 06 — Différenciation ───────────────────────────────────────


class DifferenciationData(BaseModel):
    angles_faibles: list[str] = Field(default_factory=list)
    opportunites_uniques: list[str] = Field(default_factory=list)
    angle_principal: str = ""
    facteurs_differenciation: list[str] = Field(default_factory=list)


# ─── Agent 07 — Template ──────────────────────────────────────────────


class Section(BaseModel):
    type: str  # h1, h2, h3, intro, conclusion, faq, cta, en_bref
    titre: str = ""
    contenu_guide: str = ""  # Guide de rédaction pour cette section
    obligatoire: bool = True
    ordre: int = 0


class TemplateData(BaseModel):
    template_id: str
    nom: str = ""
    structure: list[Section] = Field(default_factory=list)
    nb_sections: int = 0
    notes: str = ""


# ─── Agent 08 — Anti-cannibalisation ──────────────────────────────────


class AntiCannibData(BaseModel):
    conflit_detecte: bool = False
    pages_concurrentes: list[dict[str, Any]] = Field(default_factory=list)
    recommandation: str = ""
    action: str = "proceed"  # proceed, merge, enrich, redirect, abandon


# ─── Agent 09 — Rédaction ─────────────────────────────────────────────


class Brouillon(BaseModel):
    html: str
    word_count: int = 0
    titre: str = ""
    meta_description: str = ""
    sections: list[str] = Field(default_factory=list)


# ─── Agent 10 — SEO ───────────────────────────────────────────────────


class SeoData(BaseModel):
    title_optimise: str = ""
    meta_description_optimise: str = ""
    hn_structure: dict[str, Any] = Field(default_factory=dict)
    densite_mots_cles: dict[str, float] = Field(default_factory=dict)
    suggestions_maillage: list[dict[str, str]] = Field(default_factory=list)


# ─── Agent 11 — AEO ───────────────────────────────────────────────────


class AeoBlocks(BaseModel):
    en_bref: str = ""
    h2_questions: list[str] = Field(default_factory=list)
    faq: list[dict[str, str]] = Field(default_factory=list)
    definitions: list[dict[str, str]] = Field(default_factory=list)


# ─── Agent 12 — GEO ───────────────────────────────────────────────────


class GeoData(BaseModel):
    sources_primaires: list[dict[str, str]] = Field(default_factory=list)
    entites_nommees: list[str] = Field(default_factory=list)
    phrases_citables: list[str] = Field(default_factory=list)
    chunks: list[dict[str, str]] = Field(default_factory=list)


# ─── Agent 13 — EEAT ──────────────────────────────────────────────────


class EeatScore(BaseModel):
    score_expertise: int = Field(default=0, ge=0, le=4)
    score_experience: int = Field(default=0, ge=0, le=4)
    score_autorite: int = Field(default=0, ge=0, le=4)
    score_fiabilite: int = Field(default=0, ge=0, le=4)
    score_global: int = Field(default=0, ge=0, le=16)
    recommandations: list[str] = Field(default_factory=list)


# ─── Agent 14 — Conformité sectorielle ────────────────────────────────


class ConformiteData(BaseModel):
    valide: bool = False
    avertissements_requis: list[str] = Field(default_factory=list)
    mentions_obligatoires: list[str] = Field(default_factory=list)
    regles_appliquees: list[str] = Field(default_factory=list)
    risque_juridique: str = "faible"  # faible, modere, eleve, critique


# ─── Agent 15 — Fact-checking ─────────────────────────────────────────


class ErreurFactuelle(BaseModel):
    emplacement: str = ""
    texte_original: str = ""
    correction: str = ""
    source: str = ""
    gravite: str = "mineure"  # mineure, moderee, majeure, critique


class FactCheckData(BaseModel):
    erreurs: list[ErreurFactuelle] = Field(default_factory=list)
    corrections: list[dict[str, str]] = Field(default_factory=list)
    score_fiabilite: int = Field(default=10, ge=0, le=10)
    sources_verifiees: list[str] = Field(default_factory=list)


# ─── Agent 16 — Maillage interne ──────────────────────────────────────


class InternalLink(BaseModel):
    url_cible: str
    ancre_suggeree: str
    contexte: str = ""
    pertinence: str = "moyenne"


class InternalLinks(BaseModel):
    liens_proposes: list[InternalLink] = Field(default_factory=list)
    ancres_suggerees: list[str] = Field(default_factory=list)
    pages_pilier: list[str] = Field(default_factory=list)


# ─── Agent 17 — Maillage externe ──────────────────────────────────────


class ExternalLink(BaseModel):
    url_cible: str
    ancre: str = ""
    domaine: str = ""
    autorite: str = "moyenne"  # faible, moyenne, eleve, institutionnelle


class ExternalLinks(BaseModel):
    liens_sortants: list[ExternalLink] = Field(default_factory=list)
    sources_autorite: list[str] = Field(default_factory=list)
    pages_orphelines: list[str] = Field(default_factory=list)


# ─── Agent 18 — Multiformat ───────────────────────────────────────────


class MultiformatData(BaseModel):
    thread_linkedin: str = ""
    script_youtube: str = ""
    newsletter: str = ""
    social_posts: list[str] = Field(default_factory=list)
    session_parent: str = ""


# ─── Agent 19 — Test A/B ──────────────────────────────────────────────


class VariantAB(BaseModel):
    title: str
    meta_description: str
    ctr_predit: float = 0.0


class VariantsAB(BaseModel):
    variants: list[VariantAB] = Field(default_factory=list)
    variante_recommandee: str = ""


# ─── Agent 20 — Localisation ──────────────────────────────────────────


class LocalisedData(BaseModel):
    versions: dict[str, str] = Field(default_factory=dict)  # locale_code -> html
    hreflang_tags: str = ""
    adaptations: list[str] = Field(default_factory=list)


# ─── Agent 21 — Schema.org ────────────────────────────────────────────


class SchemaData(BaseModel):
    ld_json: str = ""
    type_schema: str = ""
    validation_errors: list[str] = Field(default_factory=list)


# ─── Agent 22 — Images ────────────────────────────────────────────────


class ImageSpec(BaseModel):
    nom: str = ""
    role: str = ""  # featured, supporting, infographie
    prompt: str = ""
    texte_alt: str = ""
    dimensions: str = "1200x630"


class ImagePlan(BaseModel):
    images: list[ImageSpec] = Field(default_factory=list)


# ─── Agent 23 — CMS Export ────────────────────────────────────────────


class ExportData(BaseModel):
    format: str = "html"  # html, wordpress, shopify, webflow
    contenu_formate: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    fichier: str = ""


# ─── Agent 24 — Mise à jour / Fraîcheur ───────────────────────────────


class RefreshPlan(BaseModel):
    date_prochaine_revision: str = ""
    frequence_jours: int = 90
    criteres_obsolescence: list[str] = Field(default_factory=list)
    sources_a_surveiller: list[str] = Field(default_factory=list)


# ─── Agent 25 — Critique Qualité ──────────────────────────────────────


class GrilleScores(BaseModel):
    lisibilite: int = Field(default=0, ge=0, le=10)
    densite_semantique: int = Field(default=0, ge=0, le=15)
    reponse_paa: int = Field(default=0, ge=0, le=20)
    originalite: int = Field(default=0, ge=0, le=15)
    fraicheur: int = Field(default=0, ge=0, le=10)
    respect_aeo: int = Field(default=0, ge=0, le=10)
    respect_geo: int = Field(default=0, ge=0, le=10)
    absence_erreurs: int = Field(default=6, ge=0, le=6)
    naturalite: int = Field(default=0, ge=0, le=4)


class ScoresFinaux(BaseModel):
    scores: GrilleScores = Field(default_factory=GrilleScores)
    score_total: int = 0
    seuil_publication: int = 75
    seuil_atteint: bool = False
    recommandation: str = ""
    blocages: list[str] = Field(default_factory=list)
    verifications_humaines: list[str] = Field(default_factory=list)


# ─── Agent 26 — Audit post-publication ────────────────────────────────


class FeedbackData(BaseModel):
    data_gsc: dict[str, Any] = Field(default_factory=dict)
    correlation: dict[str, Any] = Field(default_factory=dict)
    apprentissages: list[str] = Field(default_factory=list)
    ajustements_memoire: list[str] = Field(default_factory=list)
