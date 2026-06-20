"""Brief strategique enrichi — ajoute audience, angle, risques, SERP.

Enrichit la sortie de l'Agent 01 avec des recommandations strategiques
basees sur le mot-cle, le secteur et l'objectif.
"""

from typing import Any, Optional

from hermes.core.source_credibility import is_ymyl_secteur, YMYL_SECTEURS


def enrich_strategic_brief(
    fiche: dict[str, Any],
    keyword: str = "",
    objectif: str = "",
    secteur: Optional[str] = None,
) -> dict[str, Any]:
    """Enrichit la fiche entreprise avec un brief strategique.

    Ajoute :
    - audience_recommandee : type d'audience cible
    - angle_suggere : angle editorial recommande
    - niveau_risque : normal / YMYL / sensible
    - contraintes_redactionnelles : regles specifiques
    - objectifs_qualite : objectifs de score par type de page
    """
    brief = dict(fiche)  # Copie

    # Audience recommandee
    brief["audience_recommandee"] = _deduce_audience(keyword, objectif, secteur)

    # Angle suggere
    brief["angle_suggere"] = _deduce_angle(keyword, objectif, fiche)

    # Niveau de risque
    if is_ymyl_secteur(secteur):
        brief["niveau_risque"] = "YMYL"
        brief["contraintes_redactionnelles"] = [
            "Sources institutionnelles obligatoires (tier A ou B)",
            "Avertissement legal en fin d'article",
            "Pas de promesse de resultat",
            "Distinction claire faits / analyse editoriale",
            "Revue humaine recommandee avant publication",
        ]
    elif _is_sensible(keyword, secteur):
        brief["niveau_risque"] = "sensible"
        brief["contraintes_redactionnelles"] = [
            "Sources de qualite recommandees (tier B minimum)",
            "Verifier les affirmations chiffrees",
            "Mentionner les limites et incertitudes",
        ]
    else:
        brief["niveau_risque"] = "normal"
        brief["contraintes_redactionnelles"] = [
            "Sources varifiees recommandees",
            "Eviter les superlatifs non prouves",
        ]

    # Objectifs de qualite
    brief["objectifs_qualite"] = _quality_targets(keyword, brief.get("type_page", "article"))

    return brief


def _deduce_audience(
    keyword: str, objectif: str, secteur: Optional[str]
) -> str:
    """Deduit l'audience cible a partir du mot-cle et de l'objectif."""
    kw_lower = keyword.lower()

    if any(w in kw_lower for w in ("entreprise", "professionnel", "b2b", "pro")):
        base = "Professionnels et decideurs"
    elif any(w in kw_lower for w in ("particulier", "maison", "appartement", "famille")):
        base = "Particuliers et familles"
    elif is_ymyl_secteur(secteur):
        base = "Public concerne par un sujet sensible — ton rassurant et transparent"
    else:
        base = "Grand public interesse par le sujet"

    if objectif:
        return f"{base} — Objectif : {objectif[:100]}"
    return base


def _deduce_angle(
    keyword: str, objectif: str, fiche: dict
) -> str:
    """Deduit un angle editorial recommande."""
    kw_lower = keyword.lower()
    vau = fiche.get("valeur_ajoutee_unique", "")

    if any(w in kw_lower for w in ("meilleur", "top", "comparatif")):
        base = "Comparatif objectif avec criteres transparents"
    elif any(w in kw_lower for w in ("comment", "pourquoi", "guide")):
        base = "Guide pedagogique et actionnable"
    elif any(w in kw_lower for w in ("prix", "tarif", "devis", "cout")):
        base = "Transparence tarifaire et rapport qualite/prix"
    elif any(w in kw_lower for w in ("entreprise", "societe", "agence", "artisan")):
        base = "Expertise locale et service personnalise"
    elif objectif and "positionner" in objectif.lower():
        base = "Autorite et confiance — demontrer l'expertise locale"
    else:
        base = "Information complete et fiable"

    if vau:
        base += f" avec mise en avant de : {vau[:80]}"

    return base


def _is_sensible(keyword: str, secteur: Optional[str]) -> bool:
    """Detecte si le sujet est sensible sans etre YMYL."""
    sensible_keywords = (
        "securite", "donnee", "confidentialite", "rgpd", "assurance",
        "banque", "credit", "placement", "investissement", "retraite",
        "diete", "nutrition", "bien-etre", "medecine", "therapie",
    )
    kw_lower = keyword.lower()
    return any(w in kw_lower for w in sensible_keywords)


def _quality_targets(keyword: str, type_page: str = "article") -> dict:
    """Definit les objectifs de qualite par type de page."""
    targets = {
        "article": {"score_min": 65, "word_count_min": 600, "h2_min": 3},
        "pilier": {"score_min": 75, "word_count_min": 2000, "h2_min": 8},
        "service_local": {"score_min": 65, "word_count_min": 800, "h2_min": 4},
        "comparatif": {"score_min": 70, "word_count_min": 1500, "h2_min": 5},
        "landing": {"score_min": 65, "word_count_min": 400, "h2_min": 2},
        "fiche_produit": {"score_min": 65, "word_count_min": 400, "h2_min": 3},
        "faq": {"score_min": 60, "word_count_min": 400, "h2_min": 0},
        "news": {"score_min": 55, "word_count_min": 400, "h2_min": 2},
        "glossaire": {"score_min": 50, "word_count_min": 200, "h2_min": 0},
        "temoignage": {"score_min": 60, "word_count_min": 400, "h2_min": 2},
    }
    return targets.get(type_page, targets["article"])


# Mapping mot-cle → suggestions de format
FORMAT_SUGGESTIONS: dict[str, list[str]] = {
    "comparatif": ["Tableau comparatif", "Cas d'usage par option", "Verdict"],
    "guide": ["Table des matieres", "FAQ 8+", "Checklist", "Sources"],
    "prix": ["Grille tarifaire", "Options", "CTA devis"],
    "comment": ["Etape par etape", "Exemples concrets", "Erreurs a eviter"],
    "entreprise": ["Services detailles", "Zone d'intervention", "Temoignages", "FAQ"],
    "definition": ["Definition", "Exemple", "Sources", "Voir aussi"],
}
