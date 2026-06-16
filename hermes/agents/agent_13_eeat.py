"""Agent 13 — EEAT (Expertise, Experience, Autorite, Fiabilite).

Audite le brouillon selon les criteres EEAT de Google (Search Quality Rater Guidelines).
Chaque critere est note de 0 a 4, score global sur 16.

Skippable pour contenu non-YMYL, mais fortement recommande pour :
finance, sante, droit, cybersecurite, enfants, produits reglementes.
"""

import json
import re
from datetime import datetime
from html.parser import HTMLParser

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import EeatScore
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# ─── Grille d'evaluation heuristique ────────────────────────────────────

EEAT_CRITERES = {
    "expertise": {
        "signaux_positifs": [
            "vocabulaire technique precis", "references a des etudes",
            "citations d'experts nommes", "donnees chiffrees verificables",
            "explication de concepts complexes", "distinction entre faits et opinions",
        ],
        "signaux_negatifs": [
            "approximation", "vocabulaire vague", "absence de sources",
            "confusion entre termes techniques", "absence de profondeur",
        ],
        "poids": 0.25,
    },
    "experience": {
        "signaux_positifs": [
            "exemples concrets", "cas pratiques", "retour d'experience",
            "photos ou captures reelles", "processus decrit de l'interieur",
            "erreurs courantes mentionnees", "conseils issus de la pratique",
        ],
        "signaux_negatifs": [
            "contenu purement theorique", "absence d'exemples",
            "jamais de mention de cas reel", "ton trop scolaire ou livresque",
        ],
        "poids": 0.25,
    },
    "autorite": {
        "signaux_positifs": [
            "auteur nomme avec credentials", "entreprise reconnue dans le secteur",
            "certifications mentionnees", "prix ou distinctions",
            "presence mediatique", "partenariats institutionnels",
            "publications referencees",
        ],
        "signaux_negatifs": [
            "anonymat de l'auteur", "absence de page a propos",
            "pas de mentions legales", "site isole sans backlinks",
            "aucune preuve sociale",
        ],
        "poids": 0.25,
    },
    "fiabilite": {
        "signaux_positifs": [
            "sources citees explicitement", "dates de publication",
            "mentions legales claires", "avertissements appropries",
            "corrections ou mises a jour visibles", "transparence sur les prix",
            "contact facilement accessible",
        ],
        "signaux_negatifs": [
            "affirmations sans preuve", "promesses irrealistes",
            "absence de date", "informations perimees",
            "prix caches ou opaques", "pas de contact",
        ],
        "poids": 0.25,
    },
}


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


def _strip_html(html: str, limit: int = 5000) -> str:
    class _S(HTMLParser):
        def __init__(self):
            super().__init__()
            self.t: list[str] = []
        def handle_data(self, d):
            self.t.append(d)
    s = _S(); s.feed(html[:limit])
    return " ".join(s.t)


def _heuristic_eeat(text: str, entreprise: dict, secteur: str | None) -> EeatScore:
    """Evaluation heuristique rapide sans LLM."""
    text_lower = text.lower()
    nom = entreprise.get("nom", "")
    preuves = entreprise.get("preuves", [])
    positionnement = entreprise.get("positionnement", "")

    # Expertise : vocabulaire technique, donnees chiffrees
    expert_signals = sum(1 for s in [
        "definition", "principe", "mecanisme", "processus", "methode",
        "analyse", "statistique", "pourcentage", "selon", "d'apres",
    ] if s in text_lower)
    expertise = min(4, max(0, expert_signals // 2))

    # Experience : exemples concrets, cas pratiques
    exp_signals = sum(1 for s in [
        "par exemple", "exemple", "cas concret", "en pratique",
        "notre experience", "nous avons", "nos clients", "retour",
        "concretement", "dans la realite", "sur le terrain",
    ] if s in text_lower)
    experience = min(4, max(0, exp_signals // 2))

    # Autorite : credentials, certifications
    auth_signals = sum(1 for s in ([nom.lower()] + [p.lower() for p in preuves[:3]]
                                  + [positionnement.lower()])
                       if s and s in text_lower)
    autorite = min(4, max(1, auth_signals))  # Minimum 1 si l'entreprise est mentionnee

    # Fiabilite : sources, dates, transparence
    fiab_signals = sum(1 for s in [
        "source", "reference", "date", "mis a jour", "verifie",
        "certifie", "agree", "controle", "transparence", "contact",
        "mention", "avertissement",
    ] if s in text_lower)
    fiabilite = min(4, max(0, fiab_signals // 2))

    score_global = expertise + experience + autorite + fiabilite
    recos = []
    if expertise < 3:
        recos.append("Ajouter des references a des etudes ou des donnees chiffrees.")
    if experience < 3:
        recos.append("Inclure des exemples concrets et des cas pratiques.")
    if autorite < 3:
        recos.append("Mentionner les certifications, l'expertise de l'auteur et les preuves sociales.")
    if fiabilite < 3:
        recos.append("Ajouter des sources explicites, des dates et des mentions legales.")

    return EeatScore(
        score_expertise=expertise,
        score_experience=experience,
        score_autorite=autorite,
        score_fiabilite=fiabilite,
        score_global=score_global,
        recommandations=recos,
    )


def _build_user_message(state: SessionState, text: str) -> str:
    entreprise = state.fiche_entreprise or {}
    nom = entreprise.get("nom", "N/A")
    preuves = ", ".join(entreprise.get("preuves", [])) or "aucune"
    differenciants = ", ".join(entreprise.get("elements_differenciants", [])) or "aucun"

    return (
        f"Evalue le contenu selon les criteres EEAT de Google.\n\n"
        f"**Entreprise :** {nom}\n"
        f"**Preuves disponibles :** {preuves}\n"
        f"**Elements differenciants :** {differenciants}\n"
        f"**Secteur :** {state.config.secteur or 'N/A'}\n"
        f"**Keyword :** {state.keyword or 'N/A'}\n\n"
        f"**Contenu (extraits) :**\n{text[:2500]}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f'- score_expertise: 0-4 (profondeur technique, vocabulaire, donnees)\n'
        f'- score_experience: 0-4 (exemples concrets, cas pratiques, vecu)\n'
        f'- score_autorite: 0-4 (credentials, certifications, reconnaissance)\n'
        f'- score_fiabilite: 0-4 (sources, dates, transparence, mentions legales)\n'
        f'- score_global: 0-16 (somme des 4 scores)\n'
        f'- recommandations: ["amelioration 1", ...]'
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_13"
    agent_name = "EEAT"
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
        html = state.brouillon_html or ""
        text = _strip_html(html)
        entreprise = state.fiche_entreprise or {}
        secteur = state.config.secteur

        if state.config.dry_run:
            eeat = _heuristic_eeat(text, entreprise, secteur)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            # Heuristique d'abord, enrichie par LLM
            eeat = _heuristic_eeat(text, entreprise, secteur)

            try:
                factory = LLMFactory(
                    anthropic_api_key=config.ANTHROPIC_API_KEY,
                    openai_api_key=config.OPENAI_API_KEY,
                    deepseek_api_key=config.DEEPSEEK_API_KEY,
                    gemini_api_key=config.GEMINI_API_KEY,
                    ollama_base_url=config.OLLAMA_BASE_URL,
                    dry_run=False,
                )
                system_prompt = (
                    "Tu es un evaluateur forme aux Search Quality Rater Guidelines de Google. "
                    "Tu evalues les contenus sur les criteres EEAT : Expertise, Experience, "
                    "Autorite, Fiabilite. Sois objectif et precis. "
                    "Retourne UNIQUEMENT un objet JSON, sans texte autour."
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt,
                    user_message=_build_user_message(state, text),
                    agent_id=agent_id,
                    temperature=0.3,
                    max_tokens=1000,
                )
                data = _extract_json(llm_text)

                # Fusionner : LLM si dispo, sinon garder heuristique
                eeat = EeatScore(
                    score_expertise=data.get("score_expertise", eeat.score_expertise),
                    score_experience=data.get("score_experience", eeat.score_experience),
                    score_autorite=data.get("score_autorite", eeat.score_autorite),
                    score_fiabilite=data.get("score_fiabilite", eeat.score_fiabilite),
                    score_global=data.get("score_global", eeat.score_global),
                    recommandations=data.get("recommandations", eeat.recommandations),
                )
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                result.model_used = "heuristic-only"

        state.score_eeat = eeat.model_dump()
        result.data = state.score_eeat
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        eeat = EeatScore(score_global=0, recommandations=[f"Erreur: {e}"])
        state.score_eeat = eeat.model_dump()
        result.data = state.score_eeat
        result.status = AgentStatus.COMPLETED
        result.model_used = result.model_used or "fallback"
        result.error_message = str(e)

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
