"""Agent 08 — Anti-cannibalisation avancee.

Verifie la memoire ChromaDB pour detecter les conflits de contenu.
Compare intention, angle, mots-cles avec les contenus existants.
Skippable si aucun contenu en memoire, obligatoire si contenus existants.
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.core.memory import MemoryStore
from hermes.models.agent_data import AntiCannibData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


def _heuristic_conflict(state: SessionState, similar_docs: dict) -> tuple[bool, list[dict], str, str]:
    """Analyse heuristique des conflits sans LLM.

    Returns (conflit_detecte, pages_concurrentes, recommandation, action).
    """
    keyword = (state.keyword or "").lower()
    intention = (state.intention or "").lower()
    pages = []
    conflit = False

    documents = similar_docs.get("documents", [[]])[0] if similar_docs.get("documents") else []
    metadatas = similar_docs.get("metadatas", [[]])[0] if similar_docs.get("metadatas") else []
    distances = similar_docs.get("distances", [[]])[0] if similar_docs.get("distances") else []

    for i, doc in enumerate(documents):
        if i >= len(distances):
            continue
        distance = distances[i]
        meta = metadatas[i] if i < len(metadatas) else {}
        similarity = 1 - distance

        # Seuil : similarite > 0.7 = conflit potentiel
        is_conflict = similarity > 0.7

        if is_conflict:
            conflit = True

        pages.append({
            "content_id": meta.get("content_id", f"doc_{i}"),
            "keyword": meta.get("keyword", ""),
            "intention": meta.get("intention", ""),
            "angle": meta.get("angle", ""),
            "similarity": round(similarity, 3),
            "conflit": is_conflict,
        })

    if not conflit:
        return False, pages, "Aucun conflit detecte. Contenu suffisamment differencie.", "proceed"

    conflit_pages = [p for p in pages if p["conflit"]]
    same_intent = [p for p in conflit_pages if p.get("intention") == intention]

    if same_intent:
        # Meme mot-cle + meme intention = conflit serieux
        return (
            True, pages,
            f"{len(same_intent)} page(s) avec la meme intention. "
            f"Risque eleve de cannibalisation. Enrichir le contenu existant plutot que creer une nouvelle page.",
            "enrich",
        )

    # Meme mot-cle mais intention differente = acceptable
    return (
        False, pages,
        f"Contenu similaire detecte mais intention differente. "
        f"Bien differencier l'angle editorial.",
        "proceed",
    )


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


def _build_llm_message(state: SessionState, similar_pages: list[dict]) -> str:
    pages_text = "\n".join(
        f"  - {p.get('content_id', '?')}: keyword='{p.get('keyword', '')}', "
        f"intention='{p.get('intention', '')}', similarite={p.get('similarity', 0)}"
        for p in similar_pages[:5]
    ) or "Aucune page similaire trouvee"

    return (
        f"Analyse le risque de cannibalisation pour ce nouveau contenu.\n\n"
        f"**Nouveau mot-cle :** {state.keyword or 'N/A'}\n"
        f"**Nouvelle intention :** {state.intention or 'N/A'}\n"
        f"**Nouveau type de page :** {state.type_page or 'N/A'}\n"
        f"**Angle differenciant :** "
        f"{state.angles_differenciants.get('angle_principal', '') if state.angles_differenciants else 'N/A'}\n\n"
        f"**Pages similaires en memoire :**\n{pages_text}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f'- conflit_detecte: true/false\n'
        f'- recommandation: "explication en 1-2 phrases"\n'
        f'- action: "proceed" | "merge" | "enrich" | "redirect" | "abandon"'
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_08"
    agent_name = "Anti-cannibalisation"
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
        keyword = state.keyword or ""

        # 1. Recherche similitude dans ChromaDB
        similar_docs = {}
        try:
            mem = MemoryStore(config.CHROMA_PERSIST_DIRECTORY)
            similar_docs = mem.search_similar(keyword, n_results=5)
        except Exception:
            pass  # ChromaDB indisponible → pas de conflit

        # 2. Analyse heuristique
        conflit, pages, reco, action = _heuristic_conflict(state, similar_docs)

        # 3. Enrichissement LLM si conflit detecte (optionnel, leger)
        if conflit and not state.config.dry_run:
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
                    "Tu es un expert SEO en detection de cannibalisation. "
                    "Analyse les pages similaires et recommande la meilleure action. "
                    "Retourne UNIQUEMENT un objet JSON, sans texte autour."
                )
                texte, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt,
                    user_message=_build_llm_message(state, pages),
                    agent_id=agent_id,
                    temperature=0.3,
                    max_tokens=600,
                )
                llm_data = _extract_json(texte)
                if llm_data.get("action"):
                    action = llm_data["action"]
                if llm_data.get("recommandation"):
                    reco = llm_data["recommandation"]

                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                result.model_used = "heuristic-only"
        else:
            result.model_used = "dry-run" if state.config.dry_run else "heuristic-only"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0

        cannib = AntiCannibData(
            conflit_detecte=conflit,
            pages_concurrentes=pages,
            recommandation=reco,
            action=action,
        )

        state.anti_cannib_data = cannib.model_dump()
        result.data = state.anti_cannib_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        # Fallback : pas de conflit, on continue
        cannib = AntiCannibData(
            conflit_detecte=False,
            recommandation=f"Analyse impossible: {e}",
            action="proceed",
        )
        state.anti_cannib_data = cannib.model_dump()
        result.data = state.anti_cannib_data
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
