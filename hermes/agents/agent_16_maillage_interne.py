"""Agent 16 — Maillage interne.

Propose des liens vers d'autres contenus du site via la memoire ChromaDB.
Suggere des ancres naturelles et identifie les pages pilier a linker.
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.core.memory import MemoryStore
from hermes.models.agent_data import InternalLink, InternalLinks
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


def _mock_liens(state: SessionState, similar_docs: dict) -> InternalLinks:
    keyword = state.keyword or "le sujet"
    documents = similar_docs.get("documents", [[]])[0] if similar_docs.get("documents") else []
    metadatas = similar_docs.get("metadatas", [[]])[0] if similar_docs.get("metadatas") else []

    liens = []
    anchors_pool = [
        f"Guide complet {keyword}",
        f"Tout savoir sur {keyword}",
        f"Comparatif {keyword}",
        f"Definition {keyword}",
        "Contactez un expert",
        "Consultez nos tarifs",
        f"FAQ {keyword}",
    ]

    # Liens depuis la memoire
    for i, doc in enumerate(documents[:3]):
        meta = metadatas[i] if i < len(metadatas) else {}
        liens.append(InternalLink(
            url_cible=meta.get("url", f"/article-{i}"),
            ancre_suggeree=anchors_pool[i % len(anchors_pool)],
            contexte=f"Section pertinente sur {meta.get('keyword', keyword)}",
            pertinence="elevee",
        ))

    # Liens generiques
    liens.append(InternalLink(
        url_cible="/contact",
        ancre_suggeree="Contactez nos experts",
        contexte="Section CTA ou conclusion",
        pertinence="moyenne",
    ))
    liens.append(InternalLink(
        url_cible=f"/guide-{keyword.replace(' ', '-')}",
        ancre_suggeree=f"Guide complet : {keyword}",
        contexte="Introduction ou section definition",
        pertinence="elevee",
    ))

    return InternalLinks(
        liens_proposes=liens,
        ancres_suggerees=anchors_pool,
        pages_pilier=[f"/guide-{keyword.replace(' ', '-')}"],
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_16"
    agent_name = "Maillage interne"
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
        similar_docs = {}
        try:
            mem = MemoryStore(config.CHROMA_PERSIST_DIRECTORY)
            similar_docs = mem.search_similar(state.keyword or "", n_results=5)
        except Exception:
            pass

        if state.config.dry_run:
            liens = _mock_liens(state, similar_docs)
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
                documents = similar_docs.get("documents", [[]])[0] if similar_docs.get("documents") else []
                system_prompt = (
                    "Tu es un expert en maillage interne SEO. Propose des liens "
                    "pertinents avec des ancres naturelles et variees. "
                    "Retourne UNIQUEMENT un objet JSON, sans texte autour."
                )
                user_msg = (
                    f"Propose 3-5 liens internes pour un article sur '{state.keyword}'.\n"
                    f"Type de page: {state.type_page or 'article'}.\n"
                    f"Contenus existants: {json.dumps(documents[:3])}.\n"
                    f"Retourne UNIQUEMENT un JSON avec:\n"
                    f'- liens_proposes: [{{"url_cible": "/...", "ancre_suggeree": "...", '
                    f'"contexte": "...", "pertinence": "elevee|moyenne|faible"}}]\n'
                    f'- ancres_suggerees: ["ancre 1", ...]\n'
                    f'- pages_pilier: ["/page-pilier-1", ...]'
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt, user_message=user_msg,
                    agent_id=agent_id, temperature=0.3, max_tokens=800,
                )
                data = _extract_json(llm_text)
                liens = InternalLinks(
                    liens_proposes=[InternalLink(**l) for l in data.get("liens_proposes", [])],
                    ancres_suggerees=data.get("ancres_suggerees", []),
                    pages_pilier=data.get("pages_pilier", []),
                )
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                liens = _mock_liens(state, similar_docs)
                result.model_used = "fallback"

        state.internal_links = liens.model_dump()
        result.data = state.internal_links
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        liens = _mock_liens(state, {})
        state.internal_links = liens.model_dump()
        result.data = state.internal_links
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
