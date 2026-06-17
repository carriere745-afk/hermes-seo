"""Agent 10 — SEO.

Optimise le title, meta description, structure Hn, densite de mots-cles
et suggere le maillage interne a partir du brouillon HTML.
Non skippable — SEO obligatoire.
"""

import json
import re
from collections import Counter
from datetime import datetime
from html.parser import HTMLParser

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.models.agent_data import SeoData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState
from hermes.utils.text import compter_mots


class _HTMLStripper(HTMLParser):
    """Extrait le texte brut d'un HTML."""

    def __init__(self):
        super().__init__()
        self.text: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def _extract_headings(html: str) -> dict[str, list[str]]:
    """Extrait les titres H1, H2, H3 du HTML."""
    headings: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}
    for level in (1, 2, 3):
        pattern = rf"<h{level}[^>]*>(.*?)</h{level}>"
        headings[f"h{level}"] = re.findall(pattern, html, re.IGNORECASE | re.DOTALL)
    return headings


def _strip_html(html: str) -> str:
    """Convertit le HTML en texte brut."""
    stripper = _HTMLStripper()
    stripper.feed(html)
    return " ".join(stripper.text)


def _keyword_density(text: str, keyword: str) -> float:
    """Calcule la densite du mot-cle principal (mot ou expression)."""
    words = re.findall(r"\b\w+\b", text.lower())
    if not words:
        return 0.0
    kw_words = keyword.lower().split()
    kw_len = len(kw_words)

    if kw_len == 1:
        # Mot unique : correspondance exacte
        count = sum(1 for w in words if w == kw_words[0])
    else:
        # Expression : recherche de l'expression complete consecutive
        count = 0
        for i in range(len(words) - kw_len + 1):
            if words[i:i + kw_len] == kw_words:
                count += 1

    return round((count / len(words)) * 100, 2)


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


def _build_user_message(state: SessionState, headings: dict, word_count: int, density: float) -> str:
    keyword = state.keyword or ""
    title_current = ""
    meta_current = ""
    if state.agent_results.get("agent_09") and state.agent_results["agent_09"].data:
        data = state.agent_results["agent_09"].data
        title_current = data.get("titre", "")
        meta_current = data.get("meta_description", "")

    return (
        f"Optimise le SEO du contenu.\n\n"
        f"**Mot-cle principal :** {keyword}\n"
        f"**Intention :** {state.intention or 'N/A'}\n"
        f"**Type de page :** {state.type_page or 'N/A'}\n\n"
        f"**Titre actuel :** {title_current}\n"
        f"**Meta description actuelle :** {meta_current}\n"
        f"**Nombre de mots :** {word_count}\n"
        f"**Structure Hn :**\n"
        f"  H1 ({len(headings['h1'])}): {', '.join(h[:80] for h in headings['h1'][:3])}\n"
        f"  H2 ({len(headings['h2'])}): {', '.join(h[:60] for h in headings['h2'][:10])}\n"
        f"  H3 ({len(headings['h3'])}): {', '.join(h[:50] for h in headings['h3'][:10])}\n"
        f"**Densite mot-cle :** {density}%\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f'- title_optimise: "Titre SEO optimise (50-65 caracteres, mot-cle en debut)"\n'
        f'- meta_description_optimise: "Meta description (140-160 caracteres, CTA inclus)"\n'
        f'- hn_structure: {{"h1": "texte", "h2": ["texte", ...], "h3": ["texte", ...]}}\n'
        f'- densite_mots_cles: {{"mot-cle1": 1.5, "mot-cle2": 0.8}}\n'
        f'- suggestions_maillage: [{{"url": "/article-lie", "ancre": "texte du lien"}}]'
    )


def _mock_seo(state: SessionState) -> SeoData:
    keyword = state.keyword or "le sujet"
    html = state.brouillon_html or ""
    headings = _extract_headings(html)
    text = _strip_html(html)
    density = _keyword_density(text, keyword)

    # Title optimise
    h1 = headings["h1"][0].strip() if headings["h1"] else f"Guide {keyword}"
    title = f"{h1[:55]} | {state.fiche_entreprise.get('nom', 'Guide') if state.fiche_entreprise else 'Guide'}"[:65]

    # Meta
    meta = (
        f"Decouvrez tout sur {keyword} : definition, fonctionnement, avantages "
        f"et conseils d'experts. Guide complet et gratuit."
    )[:160]

    return SeoData(
        title_optimise=title,
        meta_description_optimise=meta,
        hn_structure={
            "h1": h1,
            "h2": [h.strip() for h in headings["h2"][:10]],
            "h3": [h.strip() for h in headings["h3"][:10]],
        },
        densite_mots_cles={
            keyword: density,
            f"{keyword} prix": round(density * 0.3, 2),
            f"{keyword} avis": round(density * 0.2, 2),
            f"meilleur {keyword}": round(density * 0.15, 2),
        },
        suggestions_maillage=[
            {"url": f"/guide-{keyword.replace(' ', '-')}", "ancre": f"Guide complet {keyword}"},
            {"url": f"/comparatif-{keyword.replace(' ', '-')}", "ancre": f"Comparatif {keyword}"},
            {"url": "/contact", "ancre": "Contactez un expert"},
        ],
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_10"
    agent_name = "SEO"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"
    html = state.brouillon_html or ""
    keyword = state.keyword or ""

    try:
        if state.config.dry_run:
            seo = _mock_seo(state)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            headings = _extract_headings(html)
            text = _strip_html(html)
            wc = compter_mots(text)
            density = _keyword_density(text, keyword)

            factory = LLMFactory(
                anthropic_api_key=config.ANTHROPIC_API_KEY,
                openai_api_key=config.OPENAI_API_KEY,
                deepseek_api_key=config.DEEPSEEK_API_KEY,
                gemini_api_key=config.GEMINI_API_KEY,
                ollama_base_url=config.OLLAMA_BASE_URL,
                dry_run=False,
            )

            system_prompt = (
                "Tu es un expert SEO on-page. Optimise le titre, la meta description, "
                "la structure Hn et les suggestions de maillage interne. "
                "Retourne UNIQUEMENT un objet JSON, sans texte autour."
            )

            texte, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=_build_user_message(state, headings, wc, density),
                agent_id=agent_id,
                temperature=0.3,
                max_tokens=1200,
            )

            data = _extract_json(texte)
            seo = SeoData(
                title_optimise=data.get("title_optimise", ""),
                meta_description_optimise=data.get("meta_description_optimise", ""),
                hn_structure=data.get("hn_structure", {}),
                densite_mots_cles=data.get("densite_mots_cles", {}),
                suggestions_maillage=data.get("suggestions_maillage", []),
            )

            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        state.seo_data = seo.model_dump()
        result.data = state.seo_data
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
