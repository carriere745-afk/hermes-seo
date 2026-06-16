"""Agent 06 — Differenciation concurrentielle.

Identifie les angles faibles des concurrents, les opportunites uniques
et l'angle principal de differenciation pour le contenu.
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.models.agent_data import DifferenciationData
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
    serp = state.serp_data or {}
    offre = state.offre_conversion_data or {}
    entreprise = state.fiche_entreprise or {}

    top_titles = "\n".join(
        f"  #{r.get('position', i+1)}: {r.get('title', '')[:120]} ({r.get('domain', '')})"
        for i, r in enumerate(serp.get("top10", [])[:10])
    ) or "Non disponible"

    concurrents = ", ".join(serp.get("concurrents_directs", [])) or "Non identifies"
    vau = offre.get("valeur_ajoutee_unique", entreprise.get("positionnement", "N/A"))

    return (
        f"Analyse la concurrence et identifie les axes de differenciation.\n\n"
        f"**Mot-cle :** {state.keyword or 'N/A'}\n"
        f"**Valeur ajoutee :** {vau}\n"
        f"**Concurrents identifies :** {concurrents}\n\n"
        f"**Top 10 SERP :**\n{top_titles}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f'- angles_faibles: ["angle 1", ...] — ce que les concurrents ne couvrent PAS bien\n'
        f'- opportunites_uniques: ["opportunite 1", ...] — ce qu\'on peut faire de mieux\n'
        f'- angle_principal: "phrase" — l\'angle editorial principal recommande\n'
        f'- facteurs_differenciation: ["facteur 1", ...] — les atouts specifiques'
    )


def _mock_differenciation(state: SessionState) -> DifferenciationData:
    entreprise = state.fiche_entreprise or {}
    offre = state.offre_conversion_data or {}
    keyword = state.keyword or "le sujet"
    differenciants = entreprise.get("elements_differenciants", [])
    preuves = offre.get("preuves", [])

    angles_faibles = [
        f"Peu de contenu approfondi sur {keyword}",
        "Manque d'exemples concrets et chiffres",
        "Absence de mise a jour recente chez les concurrents",
        "Pas de section FAQ structuree",
    ]

    opportunites = [
        f"Creer le guide le plus complet sur {keyword}",
        "Ajouter des donnees chiffrees exclusives",
        f"Inclure un comparatif detaille {keyword}",
        "Proposer des outils interactifs (simulateur, quiz)",
    ]

    angle = (
        f"Un guide exhaustif et transparent sur {keyword}, "
        f"avec des donnees verificables et des conseils d'experts"
    )

    facteurs = differenciants[:] if differenciants else [
        "Expertise metier reconnue",
        "Donnees proprietaires exclusives",
        "Approche transparente et sans jargon",
    ]

    return DifferenciationData(
        angles_faibles=angles_faibles[:5],
        opportunites_uniques=opportunites[:5],
        angle_principal=angle,
        facteurs_differenciation=facteurs[:5],
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_06"
    agent_name = "Differenciation"
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
            diff = _mock_differenciation(state)
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
                "Tu es un expert en strategie de contenu et analyse concurrentielle. "
                "A partir d'un mot-cle, de la SERP et de la fiche entreprise, "
                "tu identifies les opportunites de differenciation editoriale. "
                "Retourne UNIQUEMENT un objet JSON valide, sans texte autour."
            )

            texte, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=_build_user_message(state),
                agent_id=agent_id,
                temperature=0.5,
                max_tokens=1200,
            )

            data = _extract_json(texte)
            diff = DifferenciationData(
                angles_faibles=data.get("angles_faibles", []),
                opportunites_uniques=data.get("opportunites_uniques", []),
                angle_principal=data.get("angle_principal", ""),
                facteurs_differenciation=data.get("facteurs_differenciation", []),
            )

            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        state.angles_differenciants = diff.model_dump()
        result.data = state.angles_differenciants
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        diff = _mock_differenciation(state)
        state.angles_differenciants = diff.model_dump()
        result.data = state.angles_differenciants
        result.status = AgentStatus.COMPLETED
        result.model_used = "fallback"
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
