"""Agent 17 — Maillage externe / Netlinking editorial.

Suggere des liens sortants vers des sources d'autorite et detecte
les pages orphelines a backliner. Complementaire a l'Agent 16.
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import ExternalLink, ExternalLinks
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# Sources d'autorite generiques par secteur
AUTHORITY_SOURCES: dict[str, list[dict]] = {
    "finance": [
        {"url_cible": "https://www.service-public.fr", "domaine": "service-public.fr", "autorite": "institutionnelle"},
        {"url_cible": "https://www.amf-france.org", "domaine": "amf-france.org", "autorite": "institutionnelle"},
        {"url_cible": "https://www.banque-france.fr", "domaine": "banque-france.fr", "autorite": "institutionnelle"},
    ],
    "sante": [
        {"url_cible": "https://www.ameli.fr", "domaine": "ameli.fr", "autorite": "institutionnelle"},
        {"url_cible": "https://www.has-sante.fr", "domaine": "has-sante.fr", "autorite": "institutionnelle"},
        {"url_cible": "https://ansm.sante.fr", "domaine": "ansm.sante.fr", "autorite": "institutionnelle"},
    ],
    "droit": [
        {"url_cible": "https://www.legifrance.gouv.fr", "domaine": "legifrance.gouv.fr", "autorite": "institutionnelle"},
        {"url_cible": "https://www.service-public.fr", "domaine": "service-public.fr", "autorite": "institutionnelle"},
    ],
    "cybersecurite": [
        {"url_cible": "https://www.ssi.gouv.fr", "domaine": "ssi.gouv.fr", "autorite": "institutionnelle"},
        {"url_cible": "https://www.cnil.fr", "domaine": "cnil.fr", "autorite": "institutionnelle"},
    ],
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


def _mock_external(state: SessionState) -> ExternalLinks:
    secteur = state.config.secteur or ""
    entreprise = state.fiche_entreprise or {}
    entreprise_secteur = entreprise.get("secteur", secteur)
    serp = state.serp_data or {}

    # Sources d'autorite du secteur
    sources = AUTHORITY_SOURCES.get(entreprise_secteur, [
        {"url_cible": "https://www.service-public.fr", "domaine": "service-public.fr", "autorite": "institutionnelle"},
    ])

    liens_sortants = [ExternalLink(**s) for s in sources[:3]]

    # Ajouter des sources SERP pertinentes
    concurrents = serp.get("concurrents_directs", [])[:2]
    for c in concurrents:
        domain = c.replace("www.", "")
        liens_sortants.append(ExternalLink(
            url_cible=f"https://www.{domain}" if not domain.startswith("http") else domain,
            ancre=f"Source : {domain}",
            domaine=domain,
            autorite="elevee",
        ))

    sources_autorite = [s["url_cible"] for s in sources]

    return ExternalLinks(
        liens_sortants=liens_sortants[:5],
        sources_autorite=sources_autorite,
        pages_orphelines=[],
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_17"
    agent_name = "Maillage externe"
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
            ext = _mock_external(state)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            try:
                factory = LLMFactory(
                    anthropic_api_key=config.ANTHROPIC_API_KEY,
                    openai_api_key=config.OPENAI_API_KEY,
                    deepseek_api_key=config.DEEPSEEK_API_KEY,
                    gemini_api_key=config.GEMINI_API_KEY,
                    ollama_base_url=config.OLLAMA_BASE_URL,
                    dry_run=False,
                )
                secteur = state.config.secteur or (state.fiche_entreprise or {}).get("secteur", "")
                keyword = state.keyword or ""
                user_msg = (
                    f"Propose 3-5 liens sortants vers des sources d'autorite pour un "
                    f"article sur '{keyword}' dans le secteur {secteur}.\n"
                    f"Retourne UNIQUEMENT un JSON avec:\n"
                    f'- liens_sortants: [{{"url_cible": "https://...", "ancre": "...", '
                    f'"domaine": "...", "autorite": "institutionnelle|elevee|moyenne|faible"}}]\n'
                    f'- sources_autorite: ["https://...", ...]\n'
                    f'- pages_orphelines: ["/page-orpheline", ...]'
                )
                system_prompt = (
                    "Tu es un expert en netlinking editorial. Propose des liens sortants "
                    "vers des sources d'autorite pertinentes. Privilegie les .gouv.fr, "
                    "les organismes officiels et les etudes academiques. "
                    "Retourne UNIQUEMENT un objet JSON, sans texte autour."
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt, user_message=user_msg,
                    agent_id=agent_id, temperature=0.3, max_tokens=800,
                )
                data = _extract_json(llm_text)
                ext = ExternalLinks(
                    liens_sortants=[ExternalLink(**l) for l in data.get("liens_sortants", [])],
                    sources_autorite=data.get("sources_autorite", []),
                    pages_orphelines=data.get("pages_orphelines", []),
                )
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                ext = _mock_external(state)
                result.model_used = "fallback"

        state.external_links = ext.model_dump()
        result.data = state.external_links
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        ext = _mock_external(state)
        state.external_links = ext.model_dump()
        result.data = state.external_links
        result.status = AgentStatus.COMPLETED
        result.model_used = result.model_used or "fallback"
        result.error_message = str(e)

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    log_agent_completed(agent_id, agent_name, result.duration_ms,
                        tokens_input=result.tokens_input or 0,
                        tokens_output=result.tokens_output or 0,
                        cost_estimated=result.cost_estimated or 0.0,
                        prompt_version="v1",
                        model_used=result.model_used or "inconnu")
    state.last_completed_agent_id = agent_id
    return state


def _estimate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    from hermes.core.budget import BudgetTracker
    tracker = BudgetTracker(token_budget=0, cost_budget=0)
    return round(tracker.estimate_cost(model, tokens_input, tokens_output), 6)
