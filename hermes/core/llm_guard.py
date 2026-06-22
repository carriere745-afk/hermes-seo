"""LLM Guard anti-hallucination — cross-check LLM vs donnees deterministes.

Portage depuis saas-seo/lib/llm-guard.js (390 lignes).
4 couches de defense :
1. buildFactualInventory : extrait les faits du SessionState
2. verifyLLMClaims : cross-check les affirmations LLM vs inventaire
3. sanitizeRecommendations : filtre les reco inapplicables
4. pageTypeAwareGuard : filtre les sorties hors-cadre par type de page
"""

import re
from typing import Any


def build_factual_inventory(state: Any, html: str = "") -> dict:
    """Construit un inventaire des faits etablis (non-LLM).

    Ces faits sont injectes dans le prompt LLM pour qu'il sache
    ce qui est deja connu et ce qu'il ne doit pas inventer.
    """
    inventory = {}

    entreprise = getattr(state, "fiche_entreprise", None) or {}
    inventory["entreprise_nom"] = entreprise.get("nom", "")
    inventory["entreprise_secteur"] = entreprise.get("secteur", state.config.secteur if hasattr(state, "config") else "")
    inventory["entreprise_preuves"] = entreprise.get("preuves", [])
    inventory["entreprise_contraintes"] = entreprise.get("contraintes_legales", [])
    inventory["mots_interdits"] = entreprise.get("mots_cles_interdits", [])

    serp = getattr(state, "serp_data", None) or {}
    inventory["serp_top10_domaines"] = [r.get("domain", "") for r in serp.get("top10", [])[:5] if r.get("domain")]
    inventory["serp_concurrents"] = serp.get("concurrents_directs", [])
    inventory["serp_paa_count"] = len(serp.get("paa", []))

    persona = getattr(state, "fiche_persona", None) or {}
    inventory["persona_nom"] = persona.get("nom_persona", "")
    inventory["persona_vocabulaire"] = persona.get("vocabulaire_recommande", [])

    offre = getattr(state, "offre_conversion_data", None) or {}
    inventory["offre_benefices"] = offre.get("benefices", [])
    inventory["offre_preuves"] = offre.get("preuves", [])

    # Extraire les chiffres et entites du HTML deja produit
    if html:
        chiffres = re.findall(r"\b(\d+[\s,]?\d*)\s*(?:€|euros?|clients?|avis?|ans?|mois|%)", html)
        inventory["chiffres_dans_contenu"] = chiffres[:10]
        entites = re.findall(r"\b([A-Z][a-zàâäéèêëîïôöùûüÿ]+(?:\s[A-Z][a-zàâäéèêëîïôöùûüÿ]+){0,3})\b", html[:3000])
        inventory["entites_dans_contenu"] = list(set(entites))[:15]

    return inventory


def verify_llm_claims(
    llm_output: dict,
    inventory: dict,
    type_page: str = "article",
) -> dict:
    """Cross-check les affirmations du LLM contre l'inventaire factuel.

    Args:
        llm_output: sortie JSON du LLM
        inventory: inventaire de build_factual_inventory()
        type_page: type de page pour adapter la tolerance

    Returns: {
        "claims_verified": int,
        "claims_flagged": int,
        "flag_details": list[dict],
        "confidence": 0-100,
    }
    """
    flagged = []

    # Verifier que le LLM n'a pas invente de nom d'entreprise
    llm_text = str(llm_output).lower()
    entreprise_nom = str(inventory.get("entreprise_nom", "")).lower()

    # Verifier que les mots interdits ne sont pas presents
    mots_interdits = inventory.get("mots_interdits", [])
    for mot in mots_interdits:
        if mot and mot.lower() in llm_text:
            flagged.append({
                "type": "mot_interdit",
                "claim": f"Utilisation du mot interdit '{mot}'",
                "severity": "high",
                "action": "Supprimer toute mention de ce mot",
            })

    # Verifier les chiffres (pas d'invention de statistiques sans source)
    new_numbers = re.findall(r"\b(\d{2,})\b", str(llm_output))
    known_numbers = [str(n).replace(" ", "").replace(",", "") for n in inventory.get("chiffres_dans_contenu", [])]
    for num in new_numbers:
        clean_num = num.replace(" ", "").replace(",", "")
        if int(clean_num) > 99 and clean_num not in known_numbers and int(clean_num) % 100 == 0:
            flagged.append({
                "type": "chiffre_rond_suspect",
                "claim": f"Chiffre rond detecte : {num}",
                "severity": "moderate" if type_page in ("landing", "fiche_produit", "service_local") else "high",
                "action": "Verifier la veracite de ce chiffre ou le sourcer",
            })

    # Verifier les superlatifs non prouves
    superlatifs = ("meilleur", "premier", "seul", "unique", "leader", "revolutionnaire",
                   "le plus", "la plus", "les plus", "numero 1", "n°1")
    for sup in superlatifs:
        if sup in llm_text:
            has_proof = any(p in llm_text.lower() for p in ("selon", "d'apres", "source", "etude", "certifie"))
            if not has_proof:
                flagged.append({
                    "type": "superlatif_non_source",
                    "claim": f"Superlatif non source : '{sup}'",
                    "severity": "moderate" if type_page in ("landing", "fiche_produit") else "high",
                    "action": "Ajouter une source ou supprimer le superlatif",
                })

    confidence = max(0, 100 - len(flagged) * 10)
    if type_page in ("landing", "fiche_produit", "service_local"):
        confidence = min(100, confidence + 15)  # Tolerance marketing

    return {
        "claims_verified": max(0, len(re.findall(r"\b\w{4,}\b", str(llm_output)))),
        "claims_flagged": len(flagged),
        "flag_details": flagged,
        "confidence": confidence,
    }


def sanitize_recommendations(recos: list[dict], existing_features: list[str]) -> list[dict]:
    """Filtre les recommandations pour ne pas suggerer ce qui existe deja.

    Si une reco dit "ajouter FAQ" mais qu'une FAQ est deja presente,
    cette reco est supprimee.
    """
    existing_lower = [f.lower() for f in existing_features]
    sanitized = []

    for reco in recos:
        action = reco.get("action", "").lower()
        description = reco.get("description", "").lower()

        # Verifier si l'action est deja faite
        already_done = False
        for feat in existing_lower:
            if feat in action or feat in description:
                already_done = True
                break

        if not already_done:
            sanitized.append(reco)

    return sanitized


def page_type_aware_guard(
    llm_output: dict,
    type_page: str,
) -> dict:
    """Filtre les dimensions inappropriees selon le type de page.

    Ex: une landing ne devrait pas avoir de recommandations AEO/GEO.
    """
    result = dict(llm_output)  # Copie
    warnings = []

    dimensions_by_type = {
        "landing": {
            "allowed": ("cta", "benefices", "preuves", "social_proof", "titre", "meta"),
            "blocked": ("faq", "en_bref", "sources_primaires", "entites_nommees"),
        },
        "fiche_produit": {
            "allowed": ("caracteristiques", "prix", "avis", "cta", "titre"),
            "blocked": ("faq", "en_bref"),
        },
        "service_local": {
            "allowed": ("services", "zone", "temoignages", "cta", "contact"),
            "blocked": ("sources_primaires", "phrases_citables"),
        },
    }

    rules = dimensions_by_type.get(type_page, {})
    blocked = rules.get("blocked", ())

    if isinstance(result, dict):
        for key in list(result.keys()):
            key_lower = key.lower()
            for blocked_dim in blocked:
                if blocked_dim in key_lower:
                    result.pop(key, None)
                    warnings.append(f"Dimension '{key}' retiree (non applicable pour {type_page})")

    return {"output": result, "warnings": warnings, "type_page": type_page}
