"""Agent 03 — Analyse SERP.

Recupere les donnees SERP pour le mot-cle cible via HasData ou Serpstack.
Parse la reponse brute en SerpData structure. Utilise un LLM leger
(DeepSeek V4 Flash par defaut) pour enrichir l'analyse (PAA, concurrence).
"""

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hermes import config
from hermes.connectors.serp_api import SerpAPIClient
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.models.agent_data import SerpData, SerpResult
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# ─── Helpers ────────────────────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return url.lower()


def _parse_raw_results(raw_data: dict) -> dict[str, Any]:
    """Parse la reponse brute d'une API SERP en format intermediaire.

    Gere les formats HasData, Serpstack, et mock.
    Retourne un dict avec: organic_results, related_questions,
    featured_snippet, ai_overview.
    """
    organic = raw_data.get("organic_results", raw_data.get("results", []))

    # Normaliser chaque resultat
    parsed_results = []
    for i, item in enumerate(organic, 1):
        url = item.get("link", item.get("url", ""))
        parsed_results.append({
            "position": item.get("position", i),
            "title": item.get("title", ""),
            "url": url,
            "snippet": item.get("snippet", item.get("description", "")),
            "domain": _extract_domain(url),
            "has_featured_snippet": bool(item.get("featured_snippet")),
            "has_paa": bool(item.get("related_questions")),
            "has_ai_overview": bool(item.get("ai_overview")),
            "word_count": item.get("word_count"),
            "h2_count": item.get("h2_count"),
            "image_count": item.get("image_count"),
        })

    # PAA / questions associees
    related = raw_data.get("related_questions", raw_data.get("questions", []))
    if isinstance(related, list):
        if related and isinstance(related[0], dict):
            related = [q.get("question", q.get("title", str(q))) for q in related]
        else:
            related = [str(q) for q in related]

    # Featured snippet
    fs = raw_data.get("featured_snippet", raw_data.get("featured_snippet", {}))
    if not isinstance(fs, dict):
        fs = {}

    # AI Overview
    ai = raw_data.get("ai_overview", raw_data.get("ai_overview", {}))
    if not isinstance(ai, dict):
        ai = {}

    return {
        "organic_results": parsed_results,
        "related_questions": related,
        "featured_snippet": fs,
        "ai_overview": ai,
    }


def _enrich_with_llm(
    parsed: dict[str, Any], keyword: str, llm_text: str
) -> dict[str, Any]:
    """Enrichit les donnees SERP avec l'analyse LLM.

    Le LLM extrait les concurrents directs, les mots-cles associes,
    et les AI Overviews si non detectes par l'API.
    """
    data = _extract_json(llm_text)

    if not data.get("concurrents_directs"):
        # Fallback : top domaines
        domains = []
        for r in parsed["organic_results"][:5]:
            d = r.get("domain", "")
            if d and d not in domains:
                domains.append(d)
        data["concurrents_directs"] = domains

    if not data.get("mots_cles_associes"):
        # Fallback : PAA reformulees
        data["mots_cles_associes"] = []

    return data


def _extract_json(text: str) -> dict:
    # Bloc markdown
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Premier { }
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


def _build_user_message(parsed: dict, keyword: str) -> str:
    """Construit le message utilisateur pour le LLM d'analyse SERP."""
    top_titles = "\n".join(
        f"  #{r['position']}: {r['title'][:100]} ({r['domain']})"
        for r in parsed["organic_results"][:10]
    )
    related = "\n".join(
        f"  - {q}" for q in parsed["related_questions"][:10]
    )
    fs_content = ""
    if parsed["featured_snippet"]:
        fs_content = parsed["featured_snippet"].get(
            "content", parsed["featured_snippet"].get("title", "")
        )[:300]

    return (
        f"Analyse les donnees SERP pour le mot-cle '{keyword}'.\n\n"
        f"**Top 10 résultats :**\n{top_titles}\n\n"
        f"**Questions 'People Also Ask' :**\n{related}\n\n"
        f"**Featured Snippet :** {fs_content}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f"- concurrents_directs: liste des domaines concurrents (top 5)\n"
        f"- mots_cles_associes: 5-10 mots-cles semantiquement proches\n"
        f"- ai_overviews: liste vide si aucun AI Overview detecte\n"
        f"- search_volume: nombre entier estime ou null\n"
        f"- keyword_difficulty: 0-100 estime ou null"
    )


def _mock_serp(keyword: str, secteur: str | None = None) -> SerpData:
    """Genere des donnees SERP simulees realistes pour le dry-run."""
    slug = keyword.replace(" ", "-").lower()
    domaines_par_secteur = {
        "finance": ["service-public.fr", "lesfurets.com", "meilleurtaux.com",
                     "assurland.com", "linxea.com", "banque-france.fr",
                     "argusdelassurance.com", "quechoisir.org"],
        "sante": ["ameli.fr", "vidal.fr", "doctissimo.fr", "sante.fr",
                   "has-sante.fr", "lefigaro.fr/sante", "passeportsante.net"],
        "saas": ["hubspot.fr", "salesforce.com", "capterra.fr", "appvizer.com",
                  "zoho.com", "pipedrive.com", "notion.so"],
    }
    domaines = domaines_par_secteur.get(secteur or "saas",
                                         domaines_par_secteur["saas"])

    return SerpData(
        top10=[
            SerpResult(
                position=i,
                title=f"{['Guide complet', 'Tout savoir sur', 'Définition', 'Comparatif', 'Les meilleurs', 'Comment choisir', 'Prix', 'Avis', 'Fonctionnement', 'Alternatives'][i-1]} {keyword} {2024+i//3}",
                url=f"https://www.{domaines[i-1] if i <= len(domaines) else f'exemple{i}.fr'}/{slug}",
                snippet=f"Extrait informatif sur {keyword} - position {i}. Contenu de qualité avec données chiffrées et exemples concrets.",
                domain=domaines[i-1] if i <= len(domaines) else f"exemple{i}.fr",
                word_count=1500 + i * 200,
                h2_count=5 + i,
                image_count=2 + i % 3,
            )
            for i in range(1, 11)
        ],
        paa=[
            f"Qu'est-ce que {keyword} ?",
            f"Comment fonctionne {keyword} ?",
            f"Pourquoi {keyword} est important ?",
            f"Quels sont les avantages de {keyword} ?",
            f"Quel est le prix de {keyword} ?",
            f"Comment choisir le bon {keyword} ?",
            f"Quelles sont les alternatives à {keyword} ?",
        ],
        featured_snippets=[{
            "title": f"Définition de {keyword}",
            "content": f"{keyword.replace('-', ' ').title()} désigne l'ensemble des solutions permettant de répondre aux besoins spécifiques des utilisateurs dans ce domaine.",
        }],
        ai_overviews=[{
            "content": f"{keyword.replace('-', ' ').title()} est un sujet important. Les experts recommandent de comparer les options avant de choisir. Les critères clés incluent le prix, la qualité et le service client.",
            "sources": domaines[:3],
        }],
        concurrents_directs=domaines[:5],
        mots_cles_associes=[
            f"{keyword} prix", f"{keyword} avis", f"meilleur {keyword}",
            f"{keyword} pas cher", f"{keyword} professionnel",
            f"comment {keyword}", f"{keyword} définition",
        ],
        search_volume=880,
        keyword_difficulty=42,
    )


# ─── Agent ───────────────────────────────────────────────────────────────

async def run(state: SessionState) -> SessionState:
    agent_id = "agent_03"
    agent_name = "Analyse SERP"
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
            serp = _mock_serp(keyword, state.config.secteur)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            # 1. Appel API SERP
            client = SerpAPIClient(dry_run=False)
            raw = await client.search(keyword)
            parsed = _parse_raw_results(raw)

            # 2. Enrichissement LLM (analyse concurrentielle)
            factory = LLMFactory(
                anthropic_api_key=config.ANTHROPIC_API_KEY,
                openai_api_key=config.OPENAI_API_KEY,
                deepseek_api_key=config.DEEPSEEK_API_KEY,
                gemini_api_key=config.GEMINI_API_KEY,
                ollama_base_url=config.OLLAMA_BASE_URL,
                dry_run=False,
            )

            user_message = _build_user_message(parsed, keyword)
            system_prompt = (
                "Tu es un expert SEO qui analyse les pages de résultats Google. "
                "À partir des données SERP fournies, extrais les informations "
                "structurées demandées. Retourne UNIQUEMENT du JSON valide, "
                "sans texte autour."
            )

            llm_text, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=user_message,
                agent_id=agent_id,
                temperature=0.3,
                max_tokens=1500,
            )

            enriched = _enrich_with_llm(parsed, keyword, llm_text)

            # 3. Construire SerpData
            top10 = [
                SerpResult(
                    position=r["position"],
                    title=r["title"],
                    url=r["url"],
                    snippet=r["snippet"],
                    domain=r["domain"],
                    word_count=r.get("word_count"),
                    h2_count=r.get("h2_count"),
                    image_count=r.get("image_count"),
                )
                for r in parsed["organic_results"][:10]
            ]

            serp = SerpData(
                top10=top10,
                paa=parsed.get("related_questions", []),
                featured_snippets=[parsed["featured_snippet"]] if parsed.get("featured_snippet") else [],
                ai_overviews=[parsed["ai_overview"]] if parsed.get("ai_overview") else enriched.get("ai_overviews", []),
                concurrents_directs=enriched.get("concurrents_directs", []),
                mots_cles_associes=enriched.get("mots_cles_associes", []),
                search_volume=enriched.get("search_volume"),
                keyword_difficulty=enriched.get("keyword_difficulty"),
            )

            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        state.serp_data = serp.model_dump()
        result.data = state.serp_data
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
