"""Agent 19 — Test A/B titre & meta.

Genere 3 variantes de title et meta description, avec prediction
de CTR basee sur des heuristiques SERP (longueur, emotifs, chiffres).
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import VariantAB, VariantsAB
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


def _predict_ctr(title: str, meta: str) -> float:
    """Heuristique de prediction CTR basee sur les bonnes pratiques SEO.

    Facteurs :
    - Longueur title (ideal 50-60 caracteres)
    - Presence de chiffres dans le title
    - Presence de mots emotifs/power words
    - Longueur meta (ideal 140-155 caracteres)
    """
    score = 3.0  # CTR moyen ~3%

    # Longueur title
    t_len = len(title)
    if 40 <= t_len <= 65:
        score += 1.0
    elif t_len < 30:
        score -= 0.5

    # Chiffres dans le title
    if re.search(r"\d+", title):
        score += 0.8

    # Mots emotifs/power words
    power_words = [
        "complet", "ultime", "essentiel", "garanti", "exclusif",
        "simple", "rapide", "gratuit", "meilleur", "secret",
        "definitif", "pratique", "efficace", "comparez", "decouvrez",
        "guide", "conseils", "astuces", "erreurs a eviter",
    ]
    t_lower = title.lower()
    power_count = sum(1 for w in power_words if w in t_lower)
    score += min(1.0, power_count * 0.3)

    # Parentheses ou crochets dans le title
    if "(" in title or "[" in title:
        score += 0.3

    # Annee dans le title
    if re.search(r"\b20\d{2}\b", title):
        score += 0.5

    # Longueur meta
    m_len = len(meta)
    if 130 <= m_len <= 160:
        score += 0.5
    elif m_len > 180:
        score -= 0.3

    # CTA dans la meta
    cta_words = ["decouvrez", "apprenez", "comparez", "telechargez",
                 "essayez", "demandez", "profitez", "obtenez"]
    if any(w in meta.lower() for w in cta_words):
        score += 0.4

    return round(min(10.0, max(0.5, score)), 1)


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


def _mock_variants(state: SessionState) -> VariantsAB:
    keyword = state.keyword or "le sujet"
    seo = state.seo_data or {}
    title_base = seo.get("title_optimise", f"Guide {keyword}")
    meta_base = seo.get("meta_description_optimise", f"Decouvrez tout sur {keyword}.")

    variants = [
        VariantAB(
            title=f"{keyword.title()} : Guide Complet 2026 | Conseils Experts",
            meta_description=f"Decouvrez notre guide complet sur {keyword}. "
                            f"Definition, avantages, prix et conseils d'experts pour faire le bon choix.",
            ctr_predit=_predict_ctr(
                f"{keyword.title()} : Guide Complet 2026 | Conseils Experts",
                f"Decouvrez notre guide complet sur {keyword}. "
                f"Definition, avantages, prix et conseils d'experts pour faire le bon choix."
            ),
        ),
        VariantAB(
            title=f"{keyword.title()} en 2026 : Les 5 Choses a Savoir Avant de Choisir",
            meta_description=f"Vous voulez comparer {keyword} ? Voici les 5 criteres essentiels "
                            f"a connaitre avant de vous decider. Guide complet et gratuit.",
            ctr_predit=_predict_ctr(
                f"{keyword.title()} en 2026 : Les 5 Choses a Savoir Avant de Choisir",
                f"Vous voulez comparer {keyword} ? Voici les 5 criteres essentiels "
                f"a connaitre avant de vous decider. Guide complet et gratuit."
            ),
        ),
        VariantAB(
            title=f"Comment Bien Choisir son {keyword.title()} ? Le Guide Ultime",
            meta_description=f"Apprenez a choisir le bon {keyword} en 5 minutes. "
                            f"Comparatif, prix, avis et erreurs a eviter. ",
            ctr_predit=_predict_ctr(
                f"Comment Bien Choisir son {keyword.title()} ? Le Guide Ultime",
                f"Apprenez a choisir le bon {keyword} en 5 minutes. "
                f"Comparatif, prix, avis et erreurs a eviter."
            ),
        ),
    ]

    best = max(variants, key=lambda v: v.ctr_predit)
    return VariantsAB(variants=variants, variante_recommandee=best.title)


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_19"
    agent_name = "Test A/B"
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
            ab = _mock_variants(state)
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
                keyword = state.keyword or ""
                seo = state.seo_data or {}
                title_actuel = seo.get("title_optimise", "")
                meta_actuelle = seo.get("meta_description_optimise", "")
                user_msg = (
                    f"Genere 3 variantes de title et meta description pour A/B testing.\n"
                    f"Mot-cle: {keyword}\n"
                    f"Title actuel: {title_actuel}\nMeta actuelle: {meta_actuelle}\n"
                    f"Retourne UNIQUEMENT un JSON avec:\n"
                    f'- variants: [{{"title": "...", "meta_description": "..."}}]\n'
                )
                system_prompt = (
                    "Tu es un expert en SEO et CRO. Genere 3 variantes de balises title "
                    "et meta description pour A/B testing. Varie les formats : question, "
                    "chiffre, guide, comparatif. Retourne UNIQUEMENT un JSON."
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt, user_message=user_msg,
                    agent_id=agent_id, temperature=0.7, max_tokens=800,
                )
                data = _extract_json(llm_text)
                variants = []
                for v in data.get("variants", []):
                    ctr = _predict_ctr(v.get("title", ""), v.get("meta_description", ""))
                    variants.append(VariantAB(
                        title=v.get("title", ""),
                        meta_description=v.get("meta_description", ""),
                        ctr_predit=ctr,
                    ))
                if not variants:
                    ab = _mock_variants(state)
                else:
                    best = max(variants, key=lambda v: v.ctr_predit)
                    ab = VariantsAB(variants=variants, variante_recommandee=best.title)
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                ab = _mock_variants(state)
                result.model_used = "fallback"

        state.variants_ab = ab.model_dump()
        result.data = state.variants_ab
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        ab = _mock_variants(state)
        state.variants_ab = ab.model_dump()
        result.data = state.variants_ab
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
