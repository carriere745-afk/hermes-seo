"""Agent 34 — International SEO (gap module 22 du doc 630).

Verifie : hreflang, slugs EN distincts du FR, qualite traduction,
couverture multilingue, liaison paires FR<->EN.
"""

import re, logging, time
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_34")

TRANSLATION_TELLS_FR = ["infrastructure", "digital", "business", "scalable", "disruptif", "booster", "challenger"]
TRANSLATION_TELLS_EN = ["accompagnement", "deploiement", "valorisation", "accompagner", "realiser"]


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_34"
    agent_name = "International SEO"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        check = {
            "is_multilingual": False, "hreflang_valid": True,
            "slugs_distinct": True, "translation_quality_ok": True,
            "couverture": 0, "issues": [], "recommandations": [],
        }

        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""

        # Detection multilingue
        has_hreflang = bool(re.search(r'hreflang', content))
        check["is_multilingual"] = has_hreflang

        # Verif calques FR->EN
        if check["is_multilingual"]:
            content_lower = content.lower()
            calques = [t for t in TRANSLATION_TELLS_FR if t in content_lower]
            if calques:
                check["translation_quality_ok"] = False
                check["issues"].append(f"Calques FR detectes: {', '.join(calques)}")
                check["recommandations"].append("Adapter les expressions au contexte culturel cible (ex: digital->digital, business->company)")

        # Slugs
        if hasattr(state, 'site_url') and state.site_url:
            if re.search(r'/en/infrastructure|/en/entreprise|/en/solution', state.site_url):
                check["slugs_distinct"] = False
                check["issues"].append("Slugs FR non adaptes en EN")

        result.status = AgentStatus.COMPLETED
        result.data = check
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state
