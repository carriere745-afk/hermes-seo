"""Agent 18 — Multiformat / Recyclage.

Decline l'article final en plusieurs formats : thread LinkedIn,
script YouTube, newsletter, posts reseaux sociaux.
Reference le session_id parent pour tracer les derives.
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import MultiformatData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState
from hermes.utils.text import compter_mots


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


def _build_user_message(state: SessionState, plain_text: str) -> str:
    keyword = state.keyword or "le sujet"
    entreprise = state.fiche_entreprise or {}
    nom = entreprise.get("nom", "l'entreprise")
    offre = state.offre_conversion_data or {}
    cta = offre.get("cta_principal", "")

    return (
        f"Decline cet article en plusieurs formats de contenu.\n\n"
        f"**Mot-cle :** {keyword}\n**Entreprise :** {nom}\n"
        f"**CTA a integrer :** {cta}\n\n"
        f"**Article (extrait) :**\n{plain_text[:3000]}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f'- thread_linkedin: "Thread LinkedIn de 5-7 tweets numerotes, avec hooks et CTA final"\n'
        f'- script_youtube: "Script video YouTube (intro + 3-5 points + CTA), 2-3 min"\n'
        f'- newsletter: "Newsletter email de 200-300 mots avec sujet accrocheur"\n'
        f'- social_posts: ["Post 1", "Post 2", "Post 3"] — 3 posts courts pour X, Facebook, Instagram'
    )


def _mock_multiformat(state: SessionState) -> MultiformatData:
    keyword = state.keyword or "le sujet"
    entreprise = state.fiche_entreprise or {}
    nom = entreprise.get("nom", "L'entreprise")
    offre = state.offre_conversion_data or {}
    cta = offre.get("cta_principal", "Contactez-nous")
    vau = offre.get("valeur_ajoutee_unique", f"La solution {keyword}")

    return MultiformatData(
        session_parent=state.session_id,
        thread_linkedin=(
            f"1/ 🧵 Vous voulez tout comprendre sur {keyword} ? "
            f"Voici le guide definitif.\n\n"
            f"2/ D'abord, une definition simple :\n"
            f"{keyword} c'est [definition en 1 phrase].\n\n"
            f"3/ Les 3 choses que personne ne vous dit :\n"
            f"• [Insight 1]\n• [Insight 2]\n• [Insight 3]\n\n"
            f"4/ Le point qui fait la difference ?\n"
            f"{vau}\n\n"
            f"5/ Voici comment passer a l'action :\n"
            f"Etape 1 → [Action]\nEtape 2 → [Action]\nEtape 3 → [Action]\n\n"
            f"6/ Le resultat ? [Benefice principal]\n\n"
            f"7/ Pour aller plus loin, {cta} ↓\n"
            f"Lien dans le premier commentaire 👇"
        ),
        script_youtube=(
            f"# {keyword.upper()} : LE GUIDE COMPLET\n\n"
            f"## INTRO (30 secondes)\n"
            f"[Face camera] Vous vous demandez comment {keyword} fonctionne ? "
            f"Vous etes au bon endroit. Dans cette video, je vous explique "
            f"tout en 3 minutes.\n\n"
            f"## POINT 1 : Definition (45 secondes)\n"
            f"[Face camera + texte a l'ecran] {keyword} c'est...\n\n"
            f"## POINT 2 : Les 3 criteres essentiels (45 secondes)\n"
            f"[Split screen : 3 criteres] Quand vous choisissez {keyword}, "
            f"regardez ces 3 choses...\n\n"
            f"## POINT 3 : Erreur a eviter (30 secondes)\n"
            f"[Face camera] L'erreur que tout le monde fait...\n\n"
            f"## CTA (20 secondes)\n"
            f"[Face camera + lien en description] {cta}"
        ),
        newsletter=(
            f"**Objet :** {keyword} : tout ce que vous devez savoir en 3 minutes\n\n"
            f"Bonjour,\n\n"
            f"Vous vous etes deja demande comment bien choisir votre {keyword} ? "
            f"On a passe des heures a analyser le sujet pour vous.\n\n"
            f"Voici l'essentiel a retenir :\n"
            f"1. [Point cle 1]\n"
            f"2. [Point cle 2]\n"
            f"3. [Point cle 3]\n\n"
            f"Notre guide complet est disponible ici → [lien]\n\n"
            f"A la semaine prochaine,\n"
            f"L'equipe {nom}"
        ),
        social_posts=[
            f"🔥 {keyword} en 1 phrase ? [Definition choc]. "
            f"On vous explique tout dans notre guide. Lien en bio. #{keyword.replace(' ', '')}",
            f"Les 3 erreurs a eviter avec {keyword} :\n"
            f"1. [Erreur 1]\n2. [Erreur 2]\n3. [Erreur 3]\n"
            f"Le detail ici → [lien]",
            f"Le saviez-vous ? {keyword} peut vous faire economiser "
            f"jusqu'a [X%]. On vous explique comment. 👉 [lien]",
        ],
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_18"
    agent_name = "Multiformat"
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
        html = state.brouillon_html or ""
        from html.parser import HTMLParser
        class _S(HTMLParser):
            def __init__(self):
                super().__init__()
                self.t: list[str] = []
            def handle_data(self, d):
                self.t.append(d)
        s = _S(); s.feed(html[:8000])
        plain = " ".join(s.t)

        if state.config.dry_run:
            multi = _mock_multiformat(state)
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
                system_prompt = (
                    "Tu es un expert en content marketing et declinaison multiformat. "
                    "Tu transformes un article long en formats courts et percutants. "
                    "Retourne UNIQUEMENT un objet JSON, sans texte autour."
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt,
                    user_message=_build_user_message(state, plain),
                    agent_id=agent_id,
                    temperature=0.7,
                    max_tokens=3000,
                )
                data = _extract_json(llm_text)
                multi = MultiformatData(
                    thread_linkedin=data.get("thread_linkedin", ""),
                    script_youtube=data.get("script_youtube", ""),
                    newsletter=data.get("newsletter", ""),
                    social_posts=data.get("social_posts", []),
                    session_parent=state.session_id,
                )
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                multi = _mock_multiformat(state)
                result.model_used = "fallback"

        state.multiformat_data = multi.model_dump()
        result.data = state.multiformat_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        multi = _mock_multiformat(state)
        state.multiformat_data = multi.model_dump()
        result.data = state.multiformat_data
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
