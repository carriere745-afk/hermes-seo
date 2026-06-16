"""Agent 22 — Images.

Produit les prompts et textes alt pour 3 images (featured, supporting,
infographie) a partir du brouillon. Pas de generation d'image reelle —
l'agent prepare le brief pour un generateur (DALL-E, Midjourney, Stable Diffusion)
ou un designer humain.
"""

import json, re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import ImageSpec, ImagePlan
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


def _mock_images(state: SessionState) -> ImagePlan:
    keyword = state.keyword or "le sujet"
    entreprise = state.fiche_entreprise or {}
    nom = entreprise.get("nom", "Expert")
    type_page = state.type_page or "article"

    images = [
        ImageSpec(
            nom=f"featured-{keyword.replace(' ', '-')}",
            role="featured",
            prompt=(
                f"A professional, clean illustration representing {keyword}. "
                f"Modern style, corporate-friendly, blue and white color palette. "
                f"No text overlay. Suitable for a blog featured image."
            ),
            texte_alt=f"Illustration professionnelle representant {keyword}",
            dimensions="1200x630",
        ),
        ImageSpec(
            nom=f"supporting-{keyword.replace(' ', '-')}-1",
            role="supporting",
            prompt=(
                f"An infographic-style diagram showing the key concepts of {keyword}. "
                f"Clean design, icons for each concept, easy to understand at a glance. "
                f"Brand colors: blue, white, grey."
            ),
            texte_alt=f"Schema explicatif des concepts cles de {keyword}",
            dimensions="800x600",
        ),
        ImageSpec(
            nom=f"infographie-{keyword.replace(' ', '-')}",
            role="infographie",
            prompt=(
                f"A data visualization infographic about {keyword}. Include 4-5 key statistics "
                f"represented as charts or icons. Clean, modern, French language labels. "
                f"Source references in small text at the bottom."
            ),
            texte_alt=f"Infographie : chiffres et statistiques sur {keyword}",
            dimensions="1200x1800",
        ),
    ]

    if type_page == "fiche_produit":
        images[0] = ImageSpec(
            nom=f"product-{keyword.replace(' ', '-')}",
            role="featured",
            prompt=f"Professional product photography of {keyword} on a white background. "
                   f"Studio lighting, 3/4 angle, high resolution. No watermark.",
            texte_alt=f"Photo produit : {keyword}",
            dimensions="1200x1200",
        )

    return ImagePlan(images=images)


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_22"
    agent_name = "Images"
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
            plan = _mock_images(state)
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
                html = state.brouillon_html or ""
                from html.parser import HTMLParser
                class _S(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.t: list[str] = []
                    def handle_data(self, d):
                        self.t.append(d)
                s = _S(); s.feed(html[:5000])
                text = " ".join(s.t)

                user_msg = (
                    f"Cree 3 prompts d'image pour un article sur '{state.keyword}'.\n"
                    f"Type de page: {state.type_page or 'article'}.\n"
                    f"Contenu (extrait): {text[:1500]}\n\n"
                    f"Retourne UNIQUEMENT un JSON avec:\n"
                    f'- images: [{{"nom": "...", "role": "featured|supporting|infographie", '
                    f'"prompt": "...", "texte_alt": "...", "dimensions": "..."}}]\n'
                    f"Roles obligatoires: featured (1), supporting (1), infographie (1)."
                )
                system_prompt = (
                    "Tu es un directeur artistique specialise en illustration editoriale SEO. "
                    "Cree des prompts d'image optimises pour DALL-E/Midjourney. "
                    "Les prompts doivent etre en anglais (meilleure qualite de generation). "
                    "Les textes alt en francais. Retourne UNIQUEMENT un JSON."
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt, user_message=user_msg,
                    agent_id=agent_id, temperature=0.7, max_tokens=1500,
                )
                data = _extract_json(llm_text)
                images = [ImageSpec(**img) for img in data.get("images", [])]
                if not images:
                    plan = _mock_images(state)
                else:
                    plan = ImagePlan(images=images)
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                plan = _mock_images(state)
                result.model_used = "fallback"

        state.image_plan = plan.model_dump()
        result.data = state.image_plan
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        plan = _mock_images(state)
        state.image_plan = plan.model_dump()
        result.data = state.image_plan
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
