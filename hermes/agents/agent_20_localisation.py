"""Agent 20 — Localisation / Internationalisation.

Adapte le contenu pour plusieurs regions/pays : devises, lois locales,
intentions locales, hreflang. Conditionnellement obligatoire si
target_locales est renseigne dans la config.
"""

import json
import re
from datetime import datetime
from html.parser import HTMLParser

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import LocalisedData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# Adaptations regionales connues
LOCALE_ADAPTATIONS: dict[str, dict] = {
    "fr": {"devise": "euros (EUR)", "loi": "droit francais", "fuseau": "UTC+1", "separateur": " "},
    "fr-be": {"devise": "euros (EUR)", "loi": "droit belge", "fuseau": "UTC+1", "separateur": " "},
    "fr-ch": {"devise": "francs suisses (CHF)", "loi": "droit suisse", "fuseau": "UTC+1", "separateur": "'"},
    "fr-ca": {"devise": "dollars canadiens (CAD)", "loi": "droit quebecois/canadien", "fuseau": "UTC-5", "separateur": " "},
    "en": {"devise": "USD", "loi": "lois federales americaines", "fuseau": "UTC-5", "separateur": ","},
    "en-gb": {"devise": "livres sterling (GBP)", "loi": "droit britannique", "fuseau": "UTC+0", "separateur": ","},
    "en-ca": {"devise": "dollars canadiens (CAD)", "loi": "droit canadien", "fuseau": "UTC-5", "separateur": ","},
    "de": {"devise": "euros (EUR)", "loi": "droit allemand", "fuseau": "UTC+1", "separateur": "."},
    "es": {"devise": "euros (EUR)", "loi": "droit espagnol", "fuseau": "UTC+1", "separateur": "."},
    "it": {"devise": "euros (EUR)", "loi": "droit italien", "fuseau": "UTC+1", "separateur": "."},
    "nl": {"devise": "euros (EUR)", "loi": "droit neerlandais", "fuseau": "UTC+1", "separateur": "."},
    "pt": {"devise": "euros (EUR)", "loi": "droit portugais", "fuseau": "UTC+1", "separateur": "."},
    "jp": {"devise": "yens (JPY)", "loi": "droit japonais", "fuseau": "UTC+9", "separateur": ","},
}


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


def _build_hreflang(locales: list[str], url: str = "") -> str:
    """Construit les balises hreflang."""
    if not locales:
        return ""
    tags = []
    for loc in locales:
        if loc == "fr":
            tags.append(f'<link rel="alternate" hreflang="fr" href="{url}" />')
        else:
            tags.append(f'<link rel="alternate" hreflang="{loc}" href="{url}/{loc}/" />')
    tags.append(f'<link rel="alternate" hreflang="x-default" href="{url}" />')
    return "\n".join(tags)


def _mock_localisation(state: SessionState) -> LocalisedData:
    html = state.brouillon_html or ""
    keyword = state.keyword or "le sujet"
    locales = state.config.target_locales or ["fr-be", "fr-ch", "en"]
    url = state.config.target_url or state.site_url or "https://example.fr/article"

    versions: dict[str, str] = {}
    adaptations: list[str] = []

    for loc in locales:
        loc_info = LOCALE_ADAPTATIONS.get(loc, LOCALE_ADAPTATIONS.get("fr", {}))
        adaptations.append(
            f"{loc}: devise={loc_info['devise']}, loi={loc_info['loi']}, fuseau={loc_info['fuseau']}"
        )

        # Version localisee simplifiee
        loc_html = html
        if loc != "fr":
            # Remplacer les mentions juridiques francaises
            loc_html = loc_html.replace("droit francais", loc_info.get("loi", "droit local"))
            loc_html = loc_html.replace("en France", f"en {loc.upper()}")
            loc_html = loc_html.replace("francais", loc)
            # Ajouter une note de localisation
            loc_html += (
                f'\n<!-- Contenu localise pour {loc} -- {loc_info["devise"]}, '
                f'{loc_info["loi"]} -->'
            )

        versions[loc] = loc_html

    return LocalisedData(
        versions=versions,
        hreflang_tags=_build_hreflang(locales, url),
        adaptations=adaptations,
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_20"
    agent_name = "Localisation"
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
        locales = state.config.target_locales or []
        if not locales:
            loc_data = LocalisedData(
                adaptations=["Aucune locale cible definie — localisation non applicable."]
            )
            result.model_used = "skipped"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        elif state.config.dry_run:
            loc_data = _mock_localisation(state)
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

                class _S(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.t: list[str] = []
                    def handle_data(self, d):
                        self.t.append(d)
                s = _S(); s.feed(html[:5000])
                text = " ".join(s.t)

                user_msg = (
                    f"Adapte ce contenu pour les locales suivantes : {', '.join(locales)}.\n"
                    f"Keyword: {state.keyword}\n"
                    f"Contenu (extrait) : {text[:2000]}\n\n"
                    f"Retourne UNIQUEMENT un JSON avec:\n"
                    f'- versions: {{"locale_code": "contenu localise", ...}}\n'
                    f'- hreflang_tags: "... les balises link hreflang ..."\n'
                    f'- adaptations: ["liste des adaptations par locale", ...]'
                )
                system_prompt = (
                    "Tu es un expert en localisation de contenu. Adapte le contenu "
                    "pour chaque locale cible en tenant compte des devises, des lois "
                    "locales et des specificites culturelles. "
                    "Retourne UNIQUEMENT un objet JSON."
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt, user_message=user_msg,
                    agent_id=agent_id, temperature=0.4, max_tokens=3000,
                )
                data = _extract_json(llm_text)
                loc_data = LocalisedData(
                    versions=data.get("versions", {}),
                    hreflang_tags=data.get("hreflang_tags", _build_hreflang(
                        locales, state.config.target_url or "")),
                    adaptations=data.get("adaptations", []),
                )
                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                loc_data = _mock_localisation(state)
                result.model_used = "fallback"

        state.localised_data = loc_data.model_dump()
        result.data = state.localised_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        loc_data = _mock_localisation(state)
        state.localised_data = loc_data.model_dump()
        result.data = state.localised_data
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
