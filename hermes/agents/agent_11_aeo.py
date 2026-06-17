"""Agent 11 — AEO (Answer Engine Optimization).

Optimise le contenu pour les moteurs de reponse IA (ChatGPT, Claude,
Perplexity, Google AI Overviews, etc.).

Produit des blocs adaptes au type de page :
- Article/Pilier : En bref, H2 questions, FAQ, definitions
- Fiche produit : Fiche technique, H2 questions produit, FAQ produit
- Landing : Proposition de valeur, H2 benefices, FAQ conversion
- Comparatif : Resume comparatif, H2 criteres, FAQ methodologie
- Service local : Resume local, H2 questions locales, FAQ pratiques
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import AeoBlocks
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


def _extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except json.JSONDecodeError: pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(0))
        except json.JSONDecodeError: pass
    try: return json.loads(text.strip())
    except json.JSONDecodeError: pass
    return {}


def _build_user_message(state: SessionState) -> str:
    html = state.brouillon_html or ""
    keyword = state.keyword or ""
    type_page = state.type_page or "article"
    serp = state.serp_data or {}
    offre = state.offre_conversion_data or {}
    paa_list = serp.get("paa", [])[:10]
    ai_overview = ""
    if serp.get("ai_overviews"):
        ai_overview = serp["ai_overviews"][0].get("content", "")[:300]

    from html.parser import HTMLParser
    class _Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text: list[str] = []
        def handle_data(self, d):
            self.text.append(d)
    stripper = _Stripper()
    stripper.feed(html[:5000])
    text = " ".join(stripper.text)[:2000]

    # Instructions adaptees au type de page
    if type_page in ("fiche_produit",):
        extra = (
            f"- en_bref: \"Fiche technique rapide avec prix, specs, disponibilite (50-80 mots)\"\n"
            f"- h2_questions: [\"Questions sur le produit\", ...] — 4-6 questions typiques d'acheteur\n"
            f"- faq: [{{\"question\": \"...\", \"reponse\": \"...\"}}] — 2-3 questions/reponses\n"
            f"- definitions: [{{\"terme\": \"...\", \"definition\": \"...\"}}] — 1-3 termes techniques"
        )
    elif type_page in ("landing",):
        extra = (
            f"- en_bref: \"Proposition de valeur + benefice principal en 30-50 mots\"\n"
            f"- h2_questions: [\"Pourquoi choisir X ?\", ...] — 3-5 objections transformees en questions\n"
            f"- faq: [{{\"question\": \"...\", \"reponse\": \"...\"}}] — 2-3 questions sur l'essai/prix/resiliation\n"
            f"- definitions: [] (pas pertinent pour une landing)"
        )
    elif type_page in ("comparatif",):
        extra = (
            f"- en_bref: \"Notre selection des meilleurs {keyword} en 1-2 phrases\"\n"
            f"- h2_questions: [\"Quel est le meilleur X ?\", ...] — 4-5 questions de comparaison\n"
            f"- faq: [{{\"question\": \"...\", \"reponse\": \"...\"}}] — 2-3 questions sur la methodologie\n"
            f"- definitions: [] (pas pertinent pour un comparatif)"
        )
    elif type_page in ("service_local",):
        extra = (
            f"- en_bref: \"Service de proximite : intervention, devis gratuit, zone (50-70 mots)\"\n"
            f"- h2_questions: [\"Quel est le meilleur X pres de chez moi ?\", ...] — 3-5 questions locales\n"
            f"- faq: [{{\"question\": \"...\", \"reponse\": \"...\"}}] — 2-4 questions pratiques\n"
            f"- definitions: [] (pas pertinent pour un service local)"
        )
    else:
        extra = (
            f"- en_bref: \"Resume en 3-5 phrases courtes (80-120 mots). Repondre a la question fondamentale\"\n"
            f"- h2_questions: [\"Question 1 ?\", ...] — 5-8 H2 reformulees en questions\n"
            f"- faq: [{{\"question\": \"...\", \"reponse\": \"...\"}}] — 3-5 questions/reponses\n"
            f"- definitions: [{{\"terme\": \"...\", \"definition\": \"...\"}}] — 3-5 definitions de termes cles"
        )

    return (
        f"Optimise ce contenu {type_page} pour les moteurs de reponse IA (AEO).\n\n"
        f"**Mot-cle principal :** {keyword}\n"
        f"**Type de page :** {type_page}\n"
        f"**Intention :** {state.intention or 'N/A'}\n"
        f"**CTA principal :** {offre.get('cta_principal', 'N/A')}\n\n"
        f"**Extrait du brouillon :**\n{text}\n\n"
        f"**Questions PAA de la SERP :**\n"
        f"{chr(10).join(f'- {q}' for q in paa_list) if paa_list else 'Non disponible'}\n\n"
        f"**AI Overview concurrent :** {ai_overview or 'Non disponible'}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f"{extra}"
    )


def _mock_aeo(state: SessionState) -> AeoBlocks:
    keyword = state.keyword or "le sujet"
    type_page = state.type_page or "article"
    serp = state.serp_data or {}
    paa = serp.get("paa", [])
    offre = state.offre_conversion_data or {}

    if type_page in ("fiche_produit",):
        en_bref = (
            f"{keyword} — Fiche produit. Caracteristiques principales, prix indicatif, "
            f"avis clients. Livraison 48h, garantie 2 ans."
        )
        h2_questions = [
            f"Quelles sont les caracteristiques de {keyword} ?",
            f"Quel est le prix de {keyword} ?",
            f"Comment utiliser {keyword} ?",
            f"Quels sont les avis sur {keyword} ?",
            f"Ou acheter {keyword} au meilleur prix ?",
        ]
        faq = [
            {"question": f"{keyword} est-il compatible avec... ?",
             "reponse": f"Oui, {keyword} est compatible avec les principaux standards."},
            {"question": f"Comment installer {keyword} ?",
             "reponse": f"L'installation prend moins de 10 minutes. Guide fourni."},
        ]
        definitions = [
            {"terme": "SKU", "definition": "Identifiant unique du produit pour le suivi en stock."},
        ]
    elif type_page in ("landing",):
        vau = offre.get("valeur_ajoutee_unique", f"La solution {keyword}")
        en_bref = f"{keyword} — {vau}. Essayez gratuitement pendant 30 jours."
        h2_questions = [
            f"Pourquoi choisir {keyword} ?",
            f"Comment {keyword} resout-il votre probleme ?",
            f"Que disent nos clients de {keyword} ?",
            f"Comment demarrer avec {keyword} ?",
        ]
        faq = [
            {"question": f"Puis-je essayer {keyword} gratuitement ?",
             "reponse": f"Oui, essai gratuit de 30 jours sans engagement."},
            {"question": f"Comment resilier {keyword} ?",
             "reponse": "Resiliation en un clic depuis votre espace client."},
        ]
        definitions = []
    elif type_page in ("comparatif",):
        en_bref = (
            f"Comparatif {keyword} 2026 : notre selection des meilleures options. "
            f"Criteres : prix, fonctionnalites, service client, avis."
        )
        h2_questions = [
            f"Quel est le meilleur {keyword} en 2026 ?",
            f"Comment comparer les offres de {keyword} ?",
            f"Quel est le prix moyen de {keyword} ?",
            f"Quels criteres pour choisir {keyword} ?",
            f"{keyword} : lequel choisir selon son budget ?",
        ]
        faq = [
            {"question": f"Quel est le meilleur rapport qualite/prix pour {keyword} ?",
             "reponse": f"Notre comparatif identifie [Option A] comme le meilleur choix en 2026."},
        ]
        definitions = []
    elif type_page in ("service_local",):
        en_bref = (
            f"{keyword} — Service de proximite. Intervention sous 24h, "
            f"devis gratuit, agree assurance."
        )
        h2_questions = [
            f"Quel est le meilleur {keyword} pres de chez moi ?",
            f"Quels sont les tarifs de {keyword} ?",
            f"Comment prendre rendez-vous pour {keyword} ?",
            f"Quels sont les avis sur {keyword} ?",
        ]
        faq = [
            {"question": f"Quelle est la zone d'intervention de {keyword} ?",
             "reponse": "Nous intervenons dans un rayon de 30 km autour de notre agence."},
            {"question": "Comment obtenir un devis ?",
             "reponse": "Devis gratuit et sans engagement par telephone ou en ligne."},
        ]
        definitions = []
    else:
        en_bref = (
            f"{keyword.title().replace('-', ' ')} : tout ce qu'il faut savoir. "
            f"Definition, fonctionnement, avantages et conseils pratiques pour 2026."
        )
        h2_questions = paa[:6] if len(paa) >= 5 else [
            f"Qu'est-ce que {keyword} ?",
            f"Comment fonctionne {keyword} ?",
            f"Quels sont les avantages de {keyword} ?",
            f"Comment choisir le bon {keyword} ?",
            f"Quel est le prix de {keyword} ?",
            f"Quelles sont les erreurs a eviter avec {keyword} ?",
        ]
        faq = [
            {"question": f"Qu'est-ce que {keyword} exactement ?",
             "reponse": f"{keyword.title().replace('-', ' ')} designe l'ensemble des solutions, services ou produits lies a ce domaine."},
            {"question": f"Comment bien choisir son {keyword} ?",
             "reponse": "Comparez les options selon le prix, la qualite et les garanties."},
            {"question": f"Quels sont les pieges a eviter avec {keyword} ?",
             "reponse": "Ne pas lire les conditions, choisir uniquement sur le prix."},
            {"question": f"{keyword} est-il fait pour moi ?",
             "reponse": f"Si vous cherchez une solution fiable, {keyword} est un bon choix."},
        ]
        definitions = [
            {"terme": keyword, "definition": f"Solution ou service repondant au besoin specifique de {keyword}."},
            {"terme": f"Contrat {keyword}", "definition": f"Engagement formalisant les modalites de {keyword}."},
        ]

    return AeoBlocks(
        en_bref=en_bref,
        h2_questions=h2_questions[:8],
        faq=faq[:5],
        definitions=definitions[:5],
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_11"
    agent_name = "AEO"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"

    try:
        if state.config.dry_run:
            aeo = _mock_aeo(state)
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
            system_prompt = (
                "Tu es un expert en Answer Engine Optimization (AEO). "
                "Tu optimises le contenu pour les moteurs de reponse IA. "
                "Adapte tes sorties au type de page indique. "
                "Retourne UNIQUEMENT un objet JSON, sans texte autour."
            )
            texte, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=_build_user_message(state),
                agent_id=agent_id,
                temperature=0.3,
                max_tokens=1500,
            )
            data = _extract_json(texte)
            aeo = AeoBlocks(
                en_bref=data.get("en_bref", ""),
                h2_questions=data.get("h2_questions", []),
                faq=data.get("faq", []),
                definitions=data.get("definitions", []),
            )
            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        state.aeo_blocks = aeo.model_dump()
        result.data = state.aeo_blocks
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        result.status = AgentStatus.FAILED
        result.error_message = str(e)
        result.error_traceback = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
        state.status = "failed"
        state.error_count += 1
        result.finished_at = datetime.now()
        return state

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
