"""Agent 04 — Intention & Type de page.

Classe l'intention de recherche et deduit le type de page optimal
a partir du mot-cle et des donnees SERP. Non skippable.
Utilise un LLM leger (DeepSeek V4 Flash par defaut) + heuristiques.
"""

import json
import re
from datetime import datetime
from typing import Optional

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.models.agent_data import IntentTypeData
from hermes.models.common import AgentStatus, Intention, TypePage
from hermes.models.session import AgentResult, SessionState


# ─── Heuristiques de fallback (si pas de LLM dispo) ────────────────────

INTENT_KEYWORDS: dict[str, list[str]] = {
    "informative": [
        "comment", "qu'est-ce que", "pourquoi", "definition", "guide",
        "fonctionnement", "explication", "tutoriel", "exemple",
        "comment fonctionne", "c'est quoi", "definition de",
    ],
    "transactionnelle": [
        "acheter", "prix", "tarif", "devis", "souscrire", "commander",
        "pas cher", "promo", "livraison", "en ligne", "abonnement",
        "offre", "forfait", "reserver", "cout", "budget",
    ],
    "comparative": [
        "comparatif", "comparer", "meilleur", "vs", "versus",
        "top", "classement", "alternative", "lequel choisir",
        "quel est le meilleur", "difference entre", "ou",
    ],
    "locale": [
        "pres de chez moi", "a proximite", "dans ma ville",
        "adresse", "horaires", "telephone", "contacter",
        "agence", "boutique", "magasin", "rdv", "rendez-vous",
    ],
}

# Villes francaises et regions pour detection locale
FRENCH_CITIES: set[str] = {
    "paris", "lyon", "marseille", "toulouse", "nice", "nantes", "strasbourg",
    "montpellier", "bordeaux", "lille", "rennes", "reims", "toulon", "grenoble",
    "dijon", "angers", "nimes", "clermont", "lemans", "aix", "amiens", "limoges",
    "tours", "metz", "besancon", "perpignan", "orleans", "rouen", "mulhouse",
    "caen", "nancy", "avignon", "poitiers", "dunkerque", "pau", "calais",
    "beziers", "bourges", "chambery", "larochelle", "antibes", "cannes",
    "valence", "colmar", "frejus", "hyeres", "arles", "ales", "bayonne",
    "belfort", "blois", "chartres", "gap", "laval", "niort", "saintmalo",
    "saintetienne", "saintnazaire", "sete", "valence", "vannes",
}

REGIONS: set[str] = {
    "ile-de-france", "paca", "auvergne", "rhone-alpes", "aquitaine",
    "bretagne", "normandie", "alsace", "lorraine", "picardie", "champagne",
    "bourgogne", "centre", "limousin", "poitou", "midi-pyrenees",
    "languedoc", "roussillon", "corse", "guadeloupe", "martinique",
    "guyane", "reunion", "mayotte",
    "indre", "indre-et-loire", "loire", "loiret", "cher", "loir-et-cher",
    "eure", "eure-et-loir", "seine", "marne", "oise", "ain", "ardeche",
    "drome", "isere", "savoie", "haute-savoie", "vaucluse", "var", "alpes",
    "hautes-alpes", "alpes-maritimes", "bouches-du-rhone", "gard", "herault",
    "aude", "pyrenees", "haute-garonne", "gers", "landes", "lot", "tarn",
    "aveyron", "lozere", "cantal", "puy-de-dome", "allier", "haute-loire",
    "creuse", "correze", "haute-vienne", "vienne", "deux-sevres", "vendee",
    "morbihan", "cotes-darmor", "finistere", "ille-et-vilaine", "mayenne",
    "sarthe", "maine-et-loire", "orne", "manche", "calvados", "seine-maritime",
    "paris", "yvelines", "essonne", "hauts-de-seine", "seine-saint-denis",
    "val-de-marne", "val-doise", "seine-et-marne", "nord", "pas-de-calais",
    "somme", "aisne", "ardennes", "marne", "aube", "haute-marne", "meuse",
    "meurthe-et-moselle", "moselle", "vosges", "bas-rhin", "haut-rhin",
    "doubs", "jura", "haute-saone", "territoire-de-belfort", "yonne",
    "cote-dor", "nievre", "saone-et-loire",
}

# Patterns pour "entreprise de X [ville]" → service local
_ENTREPRISE_PATTERN = re.compile(
    r"(entreprise|societe|agence|cabinet|bureau|artisan|professionnel)s?\s+(de\s+)?[\w\s]+",
    re.IGNORECASE,
)

TYPE_BY_INTENT: dict[str, str] = {
    "informative": "article",
    "transactionnelle": "landing",
    "comparative": "comparatif",
    "locale": "service_local",
}

TYPE_OVERRIDES: dict[str, str] = {
    "pilier": "pilier",
    "guide complet": "pilier",
    "guide": "pilier",
    "fiche produit": "fiche_produit",
    "produit": "fiche_produit",
    "faq": "faq",
    "questions frequentes": "faq",
    "actualite": "news",
    "news": "news",
    "definition": "glossaire",
    "glossaire": "glossaire",
    "temoignage": "temoignage",
    "avis": "temoignage",
}


def _classify_intent_heuristic(keyword: str) -> str:
    """Classification heuristique de l'intention (sans LLM).

    Gere les cas :
    - locale : ville/region dans le mot-cle, ou "entreprise + ville"
    - transactionnelle : signaux d'achat (prix, devis, etc.)
    - comparative : comparatif, meilleur, top, etc.
    - informative : defaut
    """
    kw_lower = keyword.lower()
    scores: dict[str, int] = {}
    for intent, tokens in INTENT_KEYWORDS.items():
        score = sum(1 for t in tokens if t in kw_lower)
        scores[intent] = score

    # Boost locale si ville ou region detectee
    words = set(kw_lower.split())
    if words & FRENCH_CITIES or words & REGIONS:
        scores["locale"] = scores.get("locale", 0) + 3

    # "entreprise/societe/artisan + [mot] + ville" → tres probablement local
    if _ENTREPRISE_PATTERN.search(kw_lower) and (words & FRENCH_CITIES):
        scores["locale"] = scores.get("locale", 0) + 5
        scores["transactionnelle"] = scores.get("transactionnelle", 0) + 2  # commercial

    # "entreprise de [metier]" sans ville → commercial
    if re.match(r"entreprise\s+(de\s+)?\w+", kw_lower) and not (words & FRENCH_CITIES):
        scores["transactionnelle"] = scores.get("transactionnelle", 0) + 2

    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else "informative"


def _classify_type_heuristic(keyword: str, intent: str, serp_data: Optional[dict] = None) -> str:
    """Classification heuristique du type de page.

    Prend en compte le mot-cle, l'intention, et les donnees SERP si dispo.
    """
    kw_lower = keyword.lower()
    words = set(kw_lower.split())

    # "entreprise/societe/artisan" + ville → page de service local
    if _ENTREPRISE_PATTERN.search(kw_lower) and (words & FRENCH_CITIES):
        return "service_local"

    # Verifier les overrides explicites dans le mot-cle
    for token, page_type in TYPE_OVERRIDES.items():
        if token in kw_lower:
            if page_type == "pilier" and intent == "transactionnelle":
                return "landing"
            return page_type

    # Intent → type mapping, avec ajustements
    # locale → service_local (pas article)
    if intent == "locale":
        return "service_local"
    if intent == "transactionnelle":
        return "landing"

    # Deduire du SERP
    if serp_data:
        top10 = serp_data.get("top10", [])
        product_signals = sum(
            1 for r in top10[:5]
            if any(t in r.get("title", "").lower() for t in ["prix", "acheter", "boutique"])
        )
        if product_signals >= 3:
            return "fiche_produit"
        paa = serp_data.get("paa", [])
        if len(paa) >= 5:
            return "pilier"

    return TYPE_BY_INTENT.get(intent, "article")


def _extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    return {}


def _build_user_message(state: SessionState) -> str:
    keyword = state.keyword or ""
    serp = state.serp_data or {}

    top_titles = "\n".join(
        f"  #{r.get('position', i+1)}: {r.get('title', '')[:120]}"
        for i, r in enumerate(serp.get("top10", [])[:10])
    ) or "Non disponible"
    paa = "\n".join(f"  - {q}" for q in serp.get("paa", [])[:8]) or "Aucune"
    ai_overview = ""
    if serp.get("ai_overviews"):
        ai_overview = serp["ai_overviews"][0].get("content", "")[:300]

    return (
        f"Analyse l'intention de recherche et le type de page optimal.\n\n"
        f"**Mot-cle :** {keyword}\n\n"
        f"**Top 10 SERP :**\n{top_titles}\n\n"
        f"**People Also Ask :**\n{paa}\n\n"
        f"**AI Overview :** {ai_overview}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f"- intention: 'informative' | 'transactionnelle' | 'comparative' | 'locale' | 'navigationnelle'\n"
        f"- type_page: 'article' | 'pilier' | 'fiche_produit' | 'faq' | 'service_local' | "
        f"'comparatif' | 'landing' | 'news' | 'glossaire' | 'temoignage'\n"
        f"- justification: 1-2 phrases expliquant ton choix\n"
        f"- serp_consensus: l'intention dominante constatee dans le top 10"
    )


def _mock_intent(keyword: str, serp: Optional[dict] = None, secteur: Optional[str] = None) -> IntentTypeData:
    """Genere une classification simulee pour le dry-run."""
    intent = _classify_intent_heuristic(keyword)
    type_page = _classify_type_heuristic(keyword, intent, serp)
    serp_consensus = intent

    # Ajustements sectoriels
    if secteur == "finance":
        serp_consensus = "informative"  # La finance est tres reglementee, le top 10 est info
    elif secteur == "ecommerce":
        if intent == "informative":
            type_page = "fiche_produit"

    justifications = {
        "informative": f"Le mot-cle '{keyword}' exprime une recherche d'information. Le top 10 SERP contient majoritairement du contenu educatif.",
        "transactionnelle": f"Le mot-cle '{keyword}' contient des signaux d'achat. Les pages du top 10 sont orientees conversion.",
        "comparative": f"Le mot-cle '{keyword}' indique une comparaison. Le top 10 presente des alternatives.",
        "locale": f"Le mot-cle '{keyword}' a une intention locale. Le top 10 inclut des services de proximite.",
    }

    return IntentTypeData(
        intention=intent,
        type_page=type_page,
        justification=justifications.get(intent, f"Classification automatique basee sur le mot-cle '{keyword}'."),
        serp_consensus=serp_consensus,
    )


# ─── Agent ───────────────────────────────────────────────────────────────

async def run(state: SessionState) -> SessionState:
    agent_id = "agent_04"
    agent_name = "Intention & Type"
    start_time = datetime.now()

    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"
    keyword = state.keyword or ""

    try:
        if state.config.dry_run:
            intent_data = _mock_intent(keyword, state.serp_data, state.config.secteur)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            factory = LLMFactory(
                anthropic_api_key=config.ANTHROPIC_API_KEY,
                openai_api_key=config.OPENAI_API_KEY,
                deepseek_api_key=config.DEEPSEEK_API_KEY,
                gemini_api_key=config.GEMINI_API_KEY,
                ollama_base_url=config.OLLAMA_BASE_URL,
                dry_run=False,
            )

            user_message = _build_user_message(state)
            system_prompt = (
                "Tu es un expert SEO specialise dans l'analyse d'intention de recherche. "
                "A partir d'un mot-cle et des donnees SERP, tu classifies l'intention "
                "et recommandes le type de page optimal.\n"
                "Retourne UNIQUEMENT un objet JSON valide, sans texte autour."
            )

            texte, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=user_message,
                agent_id=agent_id,
                temperature=0.2,
                max_tokens=800,
            )

            data = _extract_json(texte)

            # Si le LLM n'a rien donne, utiliser les heuristiques
            intent = data.get("intention") or _classify_intent_heuristic(keyword)
            type_page = data.get("type_page") or _classify_type_heuristic(
                keyword, intent, state.serp_data
            )

            intent_data = IntentTypeData(
                intention=intent,
                type_page=type_page,
                justification=data.get("justification", ""),
                serp_consensus=data.get("serp_consensus", intent),
            )

            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        # Stocker dans les deux champs dedies
        state.intention = intent_data.intention
        state.type_page = intent_data.type_page
        result.data = intent_data.model_dump()
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        # Fallback ultime : heuristiques pures
        intent = _classify_intent_heuristic(keyword)
        type_page = _classify_type_heuristic(keyword, intent, state.serp_data)
        state.intention = intent
        state.type_page = type_page
        result.data = {
            "intention": intent, "type_page": type_page,
            "justification": "Fallback heuristique apres erreur LLM.",
        }
        result.status = AgentStatus.COMPLETED
        result.model_used = "heuristic-fallback"
        # Ne pas compter comme echec — l'heuristique suffit

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)

    log_agent_completed(
        agent_id, agent_name, result.duration_ms,
        tokens_input=result.tokens_input or 0,
        tokens_output=result.tokens_output or 0,
        cost_estimated=result.cost_estimated or 0.0,
        prompt_version="v1",
        model_used=result.model_used or "inconnu",
    )

    state.last_completed_agent_id = agent_id
    return state


def _estimate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    from hermes.core.budget import BudgetTracker
    tracker = BudgetTracker(token_budget=0, cost_budget=0)
    return round(tracker.estimate_cost(model, tokens_input, tokens_output), 6)
