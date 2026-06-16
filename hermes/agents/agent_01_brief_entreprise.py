"""Agent 01 — Brief Entreprise.

Extrait les informations structurées d'une entreprise à partir de son site web
et de son secteur d'activité. Utilise un LLM (DeepSeek V4 Flash par défaut)
pour l'extraction, avec validation Pydantic stricte en sortie.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.models.agent_data import FicheEntreprise
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


def _load_prompt() -> str:
    """Charge le prompt système v1 de l'Agent 01."""
    prompt_path = config.PROMPTS_DIR / "agent_01_brief_entreprise" / "v1" / "system.md"
    if prompt_path.exists():
        content = prompt_path.read_text(encoding="utf-8")
        # Enlever le frontmatter YAML (entre --- et ---)
        parts = content.split("---")
        if len(parts) >= 3:
            return parts[2].strip()
        return content.strip()
    # Fallback minimal
    return (
        "Tu es un analyste d'entreprise. À partir d'une URL et d'un secteur, "
        "extrais les informations structurées au format JSON.\n"
        "Retourne UNIQUEMENT un objet JSON avec les clés : "
        "nom, secteur, positionnement, offres, ton_marque, preuves, "
        "contraintes_legales, mots_cles_interdits, elements_differenciants."
    )


def _build_user_message(state: SessionState) -> str:
    """Construit le message utilisateur pour le LLM."""
    url = state.site_url or "Non fourni"
    secteur = state.config.secteur or "Non précisé"
    keyword = state.keyword or "Non précisé"
    objectif = state.objectif or "Non précisé"

    return (
        f"Analyse l'entreprise suivante pour la création de contenu SEO.\n\n"
        f"**URL du site :** {url}\n"
        f"**Secteur déclaré :** {secteur}\n"
        f"**Mot-clé cible :** {keyword}\n"
        f"**Objectif éditorial :** {objectif}\n\n"
        f"Retourne UNIQUEMENT un objet JSON valide, sans texte autour, "
        f"respectant exactement la structure demandée."
    )


def _extract_json(text: str) -> dict:
    """Extrait un objet JSON d'une réponse LLM potentiellement bruitée.

    Essaie plusieurs stratégies : bloc markdown, first { ... }, texte brut.
    """
    # Stratégie 1 : bloc markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Stratégie 2 : premier objet JSON dans le texte
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Stratégie 3 : texte brut comme JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    raise ValueError(
        f"Impossible d'extraire un JSON valide de la réponse LLM. "
        f"Début de la réponse : {text[:200]}..."
    )


def _mock_fiche_entreprise(session: SessionState) -> FicheEntreprise:
    """Génère une FicheEntreprise simulée pour le mode dry-run."""
    keyword = session.keyword or "test"
    secteur = session.config.secteur or "saas"
    url = session.site_url or "https://exemple.fr"

    return FicheEntreprise(
        nom=f"Entreprise Demo ({keyword})",
        secteur=secteur,
        positionnement=f"Leader de la thématique {keyword}",
        offres=[f"Solution {keyword} Premium", f"Solution {keyword} Standard"],
        ton_marque="Professionnel et accessible",
        preuves=["+1000 clients", "Note Trustpilot 4.8/5"],
        contraintes_legales=(
            ["Mentions légales obligatoires", "Avertissement réglementaire"]
            if secteur in ("finance", "sante", "droit")
            else []
        ),
        mots_cles_interdits=["gratuit", "arnaque"],
        elements_differenciants=[
            "Technologie propriétaire",
            "Service client 24/7",
            "Créé par des experts du domaine",
        ],
        url=url,
    )


async def run(state: SessionState) -> SessionState:
    """Exécute l'Agent 01 — Brief Entreprise.

    Args:
        state: SessionState avec site_url, config.secteur, keyword.

    Returns:
        SessionState modifiée avec fiche_entreprise renseignée.
    """
    agent_id = "agent_01"
    agent_name = "Brief Entreprise"
    start_time = datetime.now()

    log_agent_start(agent_id, agent_name)

    # Initialiser le résultat
    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"

    try:
        # Mode dry-run : réponse simulée
        if state.config.dry_run:
            fiche = _mock_fiche_entreprise(state)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            # Mode réel : appel LLM
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
                max_tokens=2000,
            )

            # Extraire et valider le JSON
            data = _extract_json(texte)

            # Ajouter les informations de la session que le LLM ne peut pas deviner
            if not data.get("url"):
                data["url"] = state.site_url
            if not data.get("secteur") or data["secteur"] == "Non précisé":
                data["secteur"] = state.config.secteur or "autre"

            fiche = FicheEntreprise.model_validate(data)

            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        # Stocker le résultat validé
        state.fiche_entreprise = fiche.model_dump()
        result.data = state.fiche_entreprise
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
    """Estime le coût d'un appel LLM."""
    from hermes.core.budget import BudgetTracker
    tracker = BudgetTracker(token_budget=0, cost_budget=0)
    return round(tracker.estimate_cost(model, tokens_input, tokens_output), 6)
