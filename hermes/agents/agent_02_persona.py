"""Agent 02 — Persona / Lecteur cible.

Modélise le lecteur idéal à partir de la fiche entreprise et du mot-clé.
Utilise un LLM (DeepSeek V4 Flash par défaut) pour le profiling,
avec validation Pydantic stricte en sortie.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.models.agent_data import FichePersona
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


def _load_prompt() -> str:
    prompt_path = config.PROMPTS_DIR / "agent_02_persona" / "v1" / "system.md"
    if prompt_path.exists():
        content = prompt_path.read_text(encoding="utf-8")
        parts = content.split("---")
        if len(parts) >= 3:
            return parts[2].strip()
        return content.strip()
    return (
        "Tu es un expert en profiling de lecteurs pour le marketing de contenu. "
        "À partir d'une fiche entreprise et d'un mot-clé, tu crées un persona détaillé "
        "du lecteur cible.\n"
        "Retourne UNIQUEMENT un objet JSON avec les clés : "
        "nom_persona, maturite, vocabulaire_recommande, canal_acquisition, "
        "objectif_lecture, freins, questions_typiques, niveau_expertise."
    )


def _build_user_message(state: SessionState) -> str:
    entreprise = state.fiche_entreprise or {}
    keyword = state.keyword or "Non précisé"
    objectif = state.objectif or "Non précisé"

    nom = entreprise.get("nom", "Non précisé")
    secteur = entreprise.get("secteur", "Non précisé")
    positionnement = entreprise.get("positionnement", "Non précisé")
    offres = ", ".join(entreprise.get("offres", [])) or "Non précisé"
    ton = entreprise.get("ton_marque", "Non précisé")
    preuves = ", ".join(entreprise.get("preuves", [])) or "Aucune"

    return (
        f"Crée le persona du lecteur cible pour la création de contenu SEO.\n\n"
        f"**Entreprise :** {nom}\n"
        f"**Secteur :** {secteur}\n"
        f"**Positionnement :** {positionnement}\n"
        f"**Offres :** {offres}\n"
        f"**Ton de marque :** {ton}\n"
        f"**Preuves :** {preuves}\n\n"
        f"**Mot-clé cible :** {keyword}\n"
        f"**Objectif éditorial :** {objectif}\n\n"
        f"Retourne UNIQUEMENT un objet JSON valide, sans texte autour."
    )


def _extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
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
    raise ValueError(
        f"Impossible d'extraire un JSON valide. Début : {text[:200]}..."
    )


def _mock_persona(state: SessionState) -> FichePersona:
    keyword = state.keyword or "test"
    entreprise = state.fiche_entreprise or {}
    secteur = entreprise.get("secteur", state.config.secteur or "saas")
    nom_entreprise = entreprise.get("nom", "l'entreprise")

    profils = {
        "finance": FichePersona(
            nom_persona=f"Investisseur {keyword}",
            maturite="intermediaire",
            vocabulaire_recommande=["rendement", "capital", "risque", "fiscalité", "bénéficiaire"],
            canal_acquisition="search",
            objectif_lecture="Comprendre les options avant de prendre une décision financière",
            freins=["Peur de perdre son capital", "Jargon technique", "Manque de transparence sur les frais"],
            questions_typiques=[
                f"Comment fonctionne {keyword} ?",
                f"Quels sont les avantages de {keyword} ?",
                f"Quels sont les risques de {keyword} ?",
                f"Comment choisir le bon {keyword} ?",
            ],
            niveau_expertise="intermediaire",
        ),
        "sante": FichePersona(
            nom_persona=f"Patient {keyword}",
            maturite="debutant",
            vocabulaire_recommande=["symptôme", "traitement", "prévention", "consultation", "diagnostic"],
            canal_acquisition="search",
            objectif_lecture="Trouver une solution à un problème de santé",
            freins=["Méfiance envers les solutions miracles", "Termes médicaux complexes", "Contradictions entre sources"],
            questions_typiques=[
                f"Qu'est-ce que {keyword} ?",
                f"Quels sont les symptômes de {keyword} ?",
                f"Comment traiter {keyword} ?",
            ],
            niveau_expertise="debutant",
        ),
    }

    if secteur in profils:
        return profils[secteur]

    return FichePersona(
        nom_persona=f"Prospect {keyword}",
        maturite="intermediaire",
        vocabulaire_recommande=[keyword, "solution", "comparatif", "avis", "prix"],
        canal_acquisition="search",
        objectif_lecture=f"Trouver la meilleure solution pour {keyword}",
        freins=["Manque de confiance", "Trop d'options disponibles", "Craintes sur le prix"],
        questions_typiques=[
            f"Qu'est-ce que {keyword} ?",
            f"Comment choisir le bon {keyword} ?",
            f"Quel est le prix de {keyword} ?",
            f"Quels sont les avis sur {keyword} ?",
        ],
        niveau_expertise="intermediaire",
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_02"
    agent_name = "Persona"
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
            persona = _mock_persona(state)
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

            system_prompt = _load_prompt()
            user_message = _build_user_message(state)

            texte, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=user_message,
                agent_id=agent_id,
                temperature=0.3,
                max_tokens=1500,
            )

            data = _extract_json(texte)
            persona = FichePersona.model_validate(data)

            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        state.fiche_persona = persona.model_dump()
        result.data = state.fiche_persona
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
        prompt_version=result.prompt_version or "v1",
        model_used=result.model_used or "inconnu",
    )

    state.last_completed_agent_id = agent_id
    return state


def _estimate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    from hermes.core.budget import BudgetTracker
    tracker = BudgetTracker(token_budget=0, cost_budget=0)
    return round(tracker.estimate_cost(model, tokens_input, tokens_output), 6)
