"""Agent 25 — Critique Qualite.

Applique la grille de scoring fixe (9 criteres, /100 points).
Decide de la publication ou du blocage. Non skippable — dernier rempart.
Type-aware : ponderation adaptee au type de page.
Seuil ajustable par mode qualite.
"""

import re
from datetime import datetime
from html.parser import HTMLParser

from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import GrilleScores, ScoresFinaux
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionState
from hermes.utils.text import flesch_francais, densite_semantique, compter_mots
from hermes.core.content_guard import run_quality_checks
from hermes.core.scoring_rules import get_profile, ScoreWeight, get_word_range


# Seuils de publication par mode qualite
SEUILS_PAR_MODE: dict[str, int] = {
    "fast": 65,
    "standard": 75,
    "premium": 80,
    "compliance": 85,
    "debug": 50,
}

# Ponderation type-aware : certains criteres sont non-applicables (NA)
# selon le type de page. Leur score est neutralise (max).
CRITERES_NON_APPLICABLES: dict[str, set[str]] = {
    "landing": {"reponse_paa", "respect_aeo", "respect_geo"},
    "fiche_produit": {"reponse_paa", "respect_geo"},
    "faq": {"originalite", "respect_geo"},
    "service_local": {"originalite"},
    "comparatif": {"respect_aeo"},
    "news": {"respect_aeo", "respect_geo"},
    "glossaire": {"reponse_paa", "respect_aeo"},
    "temoignage": {"reponse_paa", "respect_geo"},
}


def _strip_html(html: str) -> str:
    class _S(HTMLParser):
        def __init__(self):
            super().__init__()
            self.t: list[str] = []
        def handle_data(self, d):
            self.t.append(d)
    s = _S(); s.feed(html)
    return " ".join(s.t)


def _score_lisibilite(text: str) -> int:
    """Score lisibilite Flesch francais (0-10)."""
    score = flesch_francais(text)
    if score > 70: return 10
    if score > 50: return 8
    if score > 30: return 5
    return 0


def _score_densite(text: str) -> int:
    """Score densite semantique (0-15)."""
    d = densite_semantique(text)
    if d > 15: return 15
    if d > 10: return 12
    if d > 5: return 7
    return 0


def _score_paa(state: SessionState, text: str) -> int:
    """Score de reponse aux PAA (0-20)."""
    serp = state.serp_data or {}
    paa = serp.get("paa", [])
    if not paa:
        return 15  # Pas de PAA dispo → score neutre
    text_lower = text.lower()
    covered = sum(1 for q in paa if any(
        w.lower() in text_lower for w in q.split() if len(w) > 4
    ))
    taux = covered / len(paa)
    if taux >= 0.8: return 20
    if taux >= 0.5: return 13
    if taux >= 0.3: return 7
    return 0


def _score_originalite(state: SessionState) -> int:
    """Score originalite factuelle (0-15)."""
    diff = state.angles_differenciants or {}
    facteurs = diff.get("facteurs_differenciation", [])
    angle = diff.get("angle_principal", "")
    score = 0
    if len(facteurs) >= 3: score += 7
    elif len(facteurs) >= 1: score += 4
    if len(angle) > 20: score += 5
    if len(angle) > 50: score += 3
    return min(15, score)


def _score_fraicheur(state: SessionState) -> int:
    """Score fraicheur des sources (0-10)."""
    fact = state.fact_check_data or {}
    refresh = state.plan_refresh or {}
    freq = refresh.get("frequence_jours", 180)

    if freq <= 7: return 10
    if freq <= 30: return 10
    if freq <= 90: return 7
    if freq <= 365: return 4
    return 0


def _score_aeo(state: SessionState) -> int:
    """Score respect regles AEO (0-10)."""
    aeo = state.aeo_blocks or {}
    score = 0
    if aeo.get("en_bref"): score += 2
    h2q = aeo.get("h2_questions", [])
    if len(h2q) >= 3: score += 3
    elif len(h2q) >= 1: score += 1
    faq = aeo.get("faq", [])
    if len(faq) >= 2: score += 3
    elif len(faq) >= 1: score += 1
    definitions = aeo.get("definitions", [])
    if len(definitions) >= 2: score += 2
    elif len(definitions) >= 1: score += 1
    return min(10, score)


def _score_geo(state: SessionState) -> int:
    """Score respect regles GEO (0-10)."""
    geo = state.geo_data or {}
    score = 0
    if len(geo.get("sources_primaires", [])) >= 1: score += 3
    if len(geo.get("entites_nommees", [])) >= 3: score += 3
    elif len(geo.get("entites_nommees", [])) >= 1: score += 1
    if len(geo.get("phrases_citables", [])) >= 3: score += 2
    elif len(geo.get("phrases_citables", [])) >= 1: score += 1
    if len(geo.get("chunks", [])) >= 3: score += 2
    elif len(geo.get("chunks", [])) >= 1: score += 1
    return min(10, score)


def _score_erreurs(state: SessionState) -> int:
    """Score absence erreurs factuelles (0-6)."""
    fact = state.fact_check_data or {}
    erreurs = fact.get("erreurs", [])
    score = 6
    for e in erreurs:
        gravite = e.get("gravite", "mineure") if isinstance(e, dict) else getattr(e, "gravite", "mineure")
        if gravite == "critique":
            score = 0
            break
        if gravite == "majeure":
            score -= 2
        elif gravite == "moderee":
            score -= 1
    return max(0, min(6, score))


def _score_naturalite(state: SessionState, text: str) -> int:
    """Score naturalite du texte — estimation IA (0-4)."""
    # Heuristique : repetition de patterns typiques de l'IA
    ia_patterns = [
        r"\ben conclusion\b", r"\ben resume\b", r"\bil est important de\b",
        r"\bn'hesitez pas\b", r"\bil convient de\b", r"\ben effet\b",
        r"\bpar ailleurs\b", r"\bde plus\b", r"\bc'est pourquoi\b",
    ]
    matches = sum(1 for p in ia_patterns if len(re.findall(p, text, re.IGNORECASE)) >= 2)
    if matches <= 1: return 4
    if matches <= 3: return 2
    return 0


def _evaluate(state: SessionState) -> ScoresFinaux:
    text = _strip_html(state.brouillon_html or "")
    type_page = state.type_page or "article"

    # Calculer chaque critere
    lisibilite = _score_lisibilite(text)
    densite = _score_densite(text)
    reponse_paa = _score_paa(state, text)
    originalite = _score_originalite(state)
    fraicheur = _score_fraicheur(state)
    respect_aeo = _score_aeo(state)
    respect_geo = _score_geo(state)
    absence_erreurs = _score_erreurs(state)
    naturalite = _score_naturalite(state, text)

    # Neutraliser les criteres non-applicables via scoring_rules
    profile = get_profile(type_page)

    def _apply_weight(dim_key: str, score: int, max_val: int) -> int:
        weight_type, multiplier = profile.get_weight(dim_key)
        if weight_type == ScoreWeight.NEUTRAL:
            return max_val  # Neutralise
        if weight_type == ScoreWeight.REQUIRED:
            return min(max_val, int(score * multiplier))
        if weight_type == ScoreWeight.PENALTY:
            return min(max_val, max(0, int(score * -multiplier)))
        return min(max_val, int(score * multiplier))

    lisibilite = _apply_weight("lisibilite", lisibilite, 10)
    densite = _apply_weight("densite_semantique", densite, 15)
    reponse_paa = _apply_weight("reponse_paa", reponse_paa, 20)
    originalite = _apply_weight("originalite", originalite, 15)
    fraicheur = _apply_weight("fraicheur", fraicheur, 10)
    respect_aeo = _apply_weight("respect_aeo", respect_aeo, 10)
    respect_geo = _apply_weight("respect_geo", respect_geo, 10)
    absence_erreurs = _apply_weight("absence_erreurs", absence_erreurs, 6)
    naturalite = _apply_weight("naturalite", naturalite, 4)

    scores = GrilleScores(
        lisibilite=lisibilite,
        densite_semantique=densite,
        reponse_paa=reponse_paa,
        originalite=originalite,
        fraicheur=fraicheur,
        respect_aeo=respect_aeo,
        respect_geo=respect_geo,
        absence_erreurs=absence_erreurs,
        naturalite=naturalite,
    )

    score_total = (
        lisibilite + densite + reponse_paa + originalite + fraicheur
        + respect_aeo + respect_geo + absence_erreurs + naturalite
    )

    # ── Content guard AVANT le seuil (penalites appliquees au score) ──
    html = state.brouillon_html or ""
    type_page = state.type_page or "article"
    quality = run_quality_checks(html, type_page)

    # Blocages
    blocages: list[str] = []
    if absence_erreurs == 0:
        blocages.append("Erreur factuelle critique detectee — contenu non publiable.")
    if state.conformite_data:
        if state.conformite_data.get("risque_juridique") == "critique":
            blocages.append("Risque juridique critique — validation juridique obligatoire.")
    for b in quality.get("blocking", []):
        blocages.append(b)

    # Placeholders = penalite score (AVANT le calcul du seuil)
    if quality.get("placeholders"):
        penalty = len(quality["placeholders"]) * 3
        score_total = max(0, score_total - penalty)
        blocages.append(
            f"Placeholders generiques : {len(quality['placeholders'])} occurrence(s)"
        )

    # Seuil selon mode (APRES penalites)
    mode = state.config.mode
    seuil = SEUILS_PAR_MODE.get(mode.value if hasattr(mode, 'value') else str(mode), 75)

    seuil_atteint = score_total >= seuil

    if score_total < seuil:
        blocages.append(f"Score {score_total} < seuil {seuil}. {seuil - score_total} points manquants.")

    # Recommandation (APRES penalites)
    if score_total >= 90:
        reco = "Excellent. Contenu publiable en l'etat."
    elif score_total >= seuil:
        reco = f"Bon. Score {score_total}/{seuil}. Publiable avec corrections mineures."
    else:
        reco = f"Insuffisant. Score {score_total}/{seuil}. Corrections obligatoires avant publication."

    # Verifications humaines recommandees
    verifications: list[str] = []
    if lisibilite < 5:
        verifications.append("Lisibilite faible — simplifier les phrases.")
    if densite < 7:
        verifications.append("Densite semantique faible — enrichir le vocabulaire.")
    if fraicheur < 7:
        verifications.append("Sources vieillissantes — verifier les dates.")
    if naturalite < 4:
        verifications.append("Texte detecte comme potentiellement generee par IA — humaniser.")
    if state.config.user_skipped_agents:
        verifications.append(
            f"Agents ignores : {', '.join(state.config.user_skipped_agents)}. "
            f"Verifications humaines recommandees pour ces etapes.")
    # Verifications du content guard
    for w in quality.get("warnings", []):
        verifications.append(w)
    for ic in quality.get("internal_content", []):
        verifications.append(
            f"Contenu interne expose : '{ic['pattern']}' — "
            f"\"{ic['match'][:60]}...\" — a supprimer du contenu public"
        )
    for uc in quality.get("unsourced_claims", []):
        verifications.append(
            f"Affirmation non sourcee : '{uc['pattern']}' — "
            f"ajouter une source ou supprimer le superlatif"
        )

    # Calculer l'intervalle de confiance (± 5 points)
    marge = 5
    intervalle = f"{max(0, score_total - marge)} – {min(100, score_total + marge)}"

    return ScoresFinaux(
        scores=scores,
        score_total=score_total,
        seuil_publication=seuil,
        seuil_atteint=seuil_atteint,
        recommandation=reco,
        blocages=blocages,
        verifications_humaines=verifications,
        score_confidence="indicatif",
        intervalle_confiance=intervalle,
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_25"
    agent_name = "Critique Qualite"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"
    result.model_used = "rules-only"
    result.tokens_input = 0
    result.tokens_output = 0
    result.cost_estimated = 0.0

    try:
        scores = _evaluate(state)
        state.scores = scores.model_dump()
        result.data = state.scores
        result.status = AgentStatus.COMPLETED

        if not scores.seuil_atteint:
            state.warnings.append(
                f"[Critique Qualite] Score {scores.score_total}/{scores.seuil_publication} "
                f"— seuil non atteint. {scores.recommandation}"
            )
        for b in scores.blocages:
            state.warnings.append(f"[Critique Qualite] BLOCAGE: {b}")
    except Exception as e:
        scores = ScoresFinaux(
            score_total=0,
            recommandation=f"Erreur lors de l'evaluation: {e}",
            blocages=[f"Erreur technique: {e}"],
        )
        state.scores = scores.model_dump()
        result.data = state.scores
        result.status = AgentStatus.COMPLETED
        result.error_message = str(e)

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    log_agent_completed(agent_id, agent_name, result.duration_ms,
                        tokens_input=0, tokens_output=0,
                        cost_estimated=0.0, prompt_version="v1",
                        model_used="rules-only")
    state.last_completed_agent_id = agent_id
    return state
