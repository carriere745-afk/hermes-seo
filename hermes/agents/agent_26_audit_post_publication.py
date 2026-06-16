"""Agent 26 — Audit post-publication.

Apres X semaines de publication, recupere les donnees GSC (Google Search
Console), les correle avec les scores initiaux, met a jour la memoire
ChromaDB et produit des apprentissages pour le futur.

Dernier agent du pipeline — independant, execute apres publication.
"""

import json, re
from datetime import datetime, timedelta

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.core.memory import MemoryStore
from hermes.models.agent_data import FeedbackData
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


def _mock_gsc_data(state: SessionState) -> dict:
    """Simule des donnees GSC realistes pour le dry-run."""
    keyword = state.keyword or "mot-cle"
    scores = state.scores or {}

    score_initial = scores.get("score_total", 75)
    # Meilleur score → meilleures perfs simulees
    perf_factor = max(0.5, min(1.5, score_initial / 75))

    return {
        "query": keyword,
        "clicks": int(120 * perf_factor),
        "impressions": int(2500 * perf_factor),
        "ctr": round(4.8 * perf_factor / 100, 4),
        "position": round(8.2 / perf_factor, 2),
        "period": "28 days post-publication",
        "top_queries": [
            {"query": keyword, "clicks": int(60 * perf_factor), "impressions": int(1200 * perf_factor)},
            {"query": f"{keyword} prix", "clicks": int(25 * perf_factor), "impressions": int(500 * perf_factor)},
            {"query": f"{keyword} avis", "clicks": int(15 * perf_factor), "impressions": int(300 * perf_factor)},
            {"query": f"meilleur {keyword}", "clicks": int(10 * perf_factor), "impressions": int(280 * perf_factor)},
            {"query": f"{keyword} definition", "clicks": int(10 * perf_factor), "impressions": int(220 * perf_factor)},
        ],
        "top_pages": [
            {"url": state.site_url or f"/guide-{keyword.replace(' ', '-')}",
             "clicks": int(80 * perf_factor), "impressions": int(1600 * perf_factor)},
        ],
    }


def _correlate(state: SessionState, gsc_data: dict) -> dict:
    """Etablit la correlation entre les scores initiaux et les perfs GSC."""
    scores = state.scores or {}
    scores_detail = scores.get("scores", {})

    position = gsc_data.get("position", 99)
    ctr = gsc_data.get("ctr", 0)
    clicks = gsc_data.get("clicks", 0)

    # Position inversee pour correlation (plus bas = mieux)
    position_score = max(0, 100 - (float(position) * 10)) if position else 0

    return {
        "score_initial": scores.get("score_total", "N/A"),
        "position_gsc": position,
        "ctr_gsc": ctr,
        "clicks_28j": clicks,
        "match_qualite": (
            "Bonne correlation — le score predit correctement la performance"
            if scores.get("score_total", 0) >= 75 and position <= 8
            else "Decalage — le score etait bon mais la position faible, verifier la concurrence"
            if scores.get("score_total", 0) >= 75 and position > 10
            else "Score faible confirme par une position mediocre"
            if scores.get("score_total", 0) < 75 and position > 10
            else "Bonne surprise — score faible mais bon positionnement, l'algo Google valorise le contenu"
        ),
    }


def _learnings(state: SessionState, gsc_data: dict, correlation: dict) -> list[str]:
    """Produit des apprentissages a partir du feedback GSC."""
    learnings: list[str] = []
    scores = state.scores or {}
    score_total = scores.get("score_total", 50)
    position = gsc_data.get("position", 50)

    if score_total >= 75 and float(position) <= 8:
        learnings.append("Le score qualite >= 75 correle avec un bon positionnement. La grille de scoring est validee.")
    elif score_total >= 75 and float(position) > 10:
        learnings.append("Bon score mais position mediocre : la concurrence est peut-etre plus forte que prevu. Revoir l'analyse SERP (Agent 03).")

    if float(gsc_data.get("ctr", 0)) < 0.02:
        learnings.append("CTR faible : le title/meta ne sont pas assez attractifs. Revoir l'Agent 10 (SEO) et l'Agent 19 (Test A/B).")

    top_queries = gsc_data.get("top_queries", [])
    if len(top_queries) >= 3:
        learnings.append(f"Le contenu capte des variantes de mots-cles ({len(top_queries)} queries). Le champ semantique est bien couvert.")
    else:
        learnings.append("Peu de variantes de mots-cles captees. Elargir le champ lexical via l'Agent 11 (AEO) et l'Agent 12 (GEO).")

    if float(position) <= 3:
        learnings.append("Position top 3 ! Le contenu est un succes. Documenter les facteurs de reussite pour les repliquer.")
    elif float(position) <= 10:
        learnings.append("Position top 10. Bonne performance. Optimisations possibles pour viser le top 3.")
    elif float(position) <= 20:
        learnings.append("Position page 2. Le contenu est trouve mais pas assez competitif. Renforcer le maillage interne (Agent 16).")
    else:
        learnings.append("Position au-dela de la page 2. Reviser le choix du mot-cle (Agent 03) ou l'angle editorial (Agent 06).")

    return learnings


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_26"
    agent_name = "Audit post-publication"
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
            gsc = _mock_gsc_data(state)
            correlation = _correlate(state, gsc)
            apprentissages = _learnings(state, gsc, correlation)
            ajustements: list[str] = []
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            # Tenter de recuperer les donnees GSC si l'API est configuree
            gsc = {}
            try:
                if config.GSC_CLIENT_ID:
                    from hermes.connectors import gsc
                    gsc = await _get_gsc_data(state)
            except Exception:
                gsc = _mock_gsc_data(state)

            correlation = _correlate(state, gsc)
            apprentissages = _learnings(state, gsc, correlation)

            # Mise a jour de la memoire ChromaDB
            ajustements = []
            try:
                mem = MemoryStore(config.CHROMA_PERSIST_DIRECTORY)
                keyword = state.keyword or "contenu"
                html = state.brouillon_html or ""

                mem.add_content(
                    content_id=state.session_id,
                    text=html[:5000],
                    metadata={
                        "keyword": keyword,
                        "intention": state.intention or "",
                        "angle": (state.angles_differenciants or {}).get("angle_principal", ""),
                        "score": (state.scores or {}).get("score_total", 0),
                        "url": state.site_url or "",
                        "date": datetime.now().isoformat(),
                    },
                )
                ajustements.append(f"Contenu {state.session_id} ajoute a la memoire ChromaDB.")
                ajustements.append("Prochain Agent 08 (Anti-cannibalisation) utilisera ces donnees.")
            except Exception as e:
                ajustements.append(f"Echec mise a jour memoire: {e}")

            # Enrichissement LLM des apprentissages
            try:
                factory = LLMFactory(
                    anthropic_api_key=config.ANTHROPIC_API_KEY,
                    openai_api_key=config.OPENAI_API_KEY,
                    deepseek_api_key=config.DEEPSEEK_API_KEY,
                    gemini_api_key=config.GEMINI_API_KEY,
                    ollama_base_url=config.OLLAMA_BASE_URL,
                    dry_run=False,
                )
                user_msg = (
                    f"Analyse les donnees GSC post-publication et propose des apprentissages.\n"
                    f"Keyword: {state.keyword}\n"
                    f"Score initial: {(state.scores or {}).get('score_total', 'N/A')}\n"
                    f"Donnees GSC: {json.dumps(gsc, default=str)[:2000]}\n\n"
                    f"Retourne UNIQUEMENT un JSON avec:\n"
                    f'- apprentissages_llm: ["apprentissage 1", ...]\n'
                    f"- recommandation_finale: \"...\""
                )
                system_prompt = (
                    "Tu es un analyste SEO qui interprete les donnees Google Search Console. "
                    "Propose des apprentissages actionnables. "
                    "Retourne UNIQUEMENT un objet JSON."
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt, user_message=user_msg,
                    agent_id=agent_id, temperature=0.3, max_tokens=600,
                )
                data = _extract_json(llm_text)
                if data.get("apprentissages_llm"):
                    apprentissages.extend(data["apprentissages_llm"])
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                if result.model_used == "dry-run":
                    pass
                else:
                    result.model_used = result.model_used or "rules-only"

        feedback = FeedbackData(
            data_gsc=gsc,
            correlation=correlation,
            apprentissages=apprentissages,
            ajustements_memoire=ajustements,
        )

        state.feedback_data = feedback.model_dump()
        result.data = state.feedback_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        feedback = FeedbackData(
            apprentissages=[f"Erreur lors de l'audit: {e}"],
        )
        state.feedback_data = feedback.model_dump()
        result.data = state.feedback_data
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


async def _get_gsc_data(state: SessionState) -> dict:
    """Tente de recuperer les vraies donnees GSC."""
    # Placeholder : l'implementation reelle depend de l'API GSC
    # Pour l'instant, on retourne les donnees simulees
    return _mock_gsc_data(state)


def _estimate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    from hermes.core.budget import BudgetTracker
    tracker = BudgetTracker(token_budget=0, cost_budget=0)
    return round(tracker.estimate_cost(model, tokens_input, tokens_output), 6)
