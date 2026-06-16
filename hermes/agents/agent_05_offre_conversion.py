"""Agent 05 — Offre & Conversion.

Definit les benefices, objections, preuves et CTA pour le contenu.
Combine les insights de la fiche entreprise, du persona, et de l'intention
pour produire une strategie de conversion alignee.
Utilise un LLM leger (DeepSeek V4 Flash) + fallback heuristique.
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.models.agent_data import OffreConversion
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
    entreprise = state.fiche_entreprise or {}
    persona = state.fiche_persona or {}

    return (
        "Definis la strategie de conversion pour le contenu editorial.\n\n"
        f"**Entreprise :** {entreprise.get('nom', 'N/A')}\n"
        f"**Secteur :** {entreprise.get('secteur', state.config.secteur or 'N/A')}\n"
        f"**Positionnement :** {entreprise.get('positionnement', 'N/A')}\n"
        f"**Offres :** {', '.join(entreprise.get('offres', [])) or 'N/A'}\n"
        f"**Elements differenciants :** {', '.join(entreprise.get('elements_differenciants', [])) or 'N/A'}\n\n"
        f"**Persona :** {persona.get('nom_persona', 'N/A')} "
        f"(maturite: {persona.get('maturite', 'N/A')})\n"
        f"**Freins :** {', '.join(persona.get('freins', [])) or 'N/A'}\n"
        f"**Objectif de lecture :** {persona.get('objectif_lecture', 'N/A')}\n\n"
        f"**Mot-cle :** {state.keyword or 'N/A'}\n"
        f"**Intention :** {state.intention or 'N/A'}\n"
        f"**Type de page :** {state.type_page or 'N/A'}\n\n"
        "Retourne UNIQUEMENT un objet JSON avec :\n"
        '- benefices: ["benefice 1", ...] — 3-5 benefices concrets du produit/service\n'
        '- objections: ["objection 1", ...] — 3-5 objections que le lecteur pourrait avoir\n'
        '- preuves: ["preuve 1", ...] — 3-5 preuves de credibilite\n'
        '- cta_principal: "texte" — le call-to-action principal\n'
        '- cta_secondaire: "texte" — un CTA secondaire plus doux\n'
        '- valeur_ajoutee_unique: "texte" — la promesse unique en 1 phrase'
    )


def _mock_offre(state: SessionState) -> OffreConversion:
    entreprise = state.fiche_entreprise or {}
    persona = state.fiche_persona or {}
    keyword = state.keyword or "le service"
    intention = state.intention or "informative"
    offres = entreprise.get("offres", [f"Solution {keyword}"])
    preuves_entreprise = entreprise.get("preuves", [])
    differenciants = entreprise.get("elements_differenciants", [])

    # Benefices alignes sur les offres
    benefices = [f"Gagnez du temps grace a {offres[0]}" if offres else f"Solution complete pour {keyword}"]
    benefices.append(f"Reduction des couts jusqu'a 30%")
    benefices.append(f"Accompagnement personnalise par des experts")

    # Objections alignees sur les freins du persona
    objections = persona.get("freins", [])[:]
    if not objections:
        objections = ["Est-ce vraiment utile ?", "Le prix est-il justifie ?", "Est-ce complique a mettre en place ?"]

    # Preuves
    preuves = preuves_entreprise[:] if preuves_entreprise else [
        "+1000 clients satisfaits", "Note Trustpilot 4.8/5", "Certification professionnelle"
    ]

    # CTA selon intention
    if intention in ("transactionnelle", "comparative"):
        cta = f"Demandez votre devis {keyword} gratuit"
        cta2 = "Comparez les offres"
    else:
        cta = f"Telechargez notre guide complet sur {keyword}"
        cta2 = "Contactez un expert"

    # Valeur ajoutee
    if differenciants:
        vau = differenciants[0]
    else:
        vau = f"La seule solution {keyword} qui combine performance et simplicite"

    return OffreConversion(
        benefices=benefices[:5],
        objections=objections[:5],
        preuves=preuves[:5],
        cta_principal=cta,
        cta_secondaire=cta2,
        valeur_ajoutee_unique=vau,
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_05"
    agent_name = "Offre & Conversion"
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
            offre = _mock_offre(state)
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

            user_message = _build_user_message(state)
            system_prompt = (
                "Tu es un expert en strategie de conversion et copywriting. "
                "A partir des informations fournies, tu definis les benefices, "
                "objections, preuves et calls-to-action pour un contenu editorial. "
                "Retourne UNIQUEMENT un objet JSON valide, sans texte autour."
            )

            texte, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=user_message,
                agent_id=agent_id,
                temperature=0.4,
                max_tokens=1200,
            )

            data = _extract_json(texte)
            offre = OffreConversion(
                benefices=data.get("benefices", []),
                objections=data.get("objections", []),
                preuves=data.get("preuves", []),
                cta_principal=data.get("cta_principal", ""),
                cta_secondaire=data.get("cta_secondaire", ""),
                valeur_ajoutee_unique=data.get("valeur_ajoutee_unique", ""),
            )

            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        state.offre_conversion_data = offre.model_dump()
        result.data = state.offre_conversion_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        # Fallback : mock avec donnees disponibles
        offre = _mock_offre(state)
        state.offre_conversion_data = offre.model_dump()
        result.data = state.offre_conversion_data
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
