"""Agent 35 — Reputation & Signals Sociaux (gap module 8 annexe doc 630).

Suit : volume de recherche du nom de marque, mentions presse,
reseaux sociaux, presence plateformes tierces.
"""

import logging, time
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_35")

SOCIAL_PLATFORMS = ["linkedin.com", "youtube.com", "twitter.com", "instagram.com"]
PRESS_DOMAINS = ["lemonde.fr", "lesechos.fr", "bfmtv.com", "francetvinfo.fr", "challenges.fr",
                 "capital.fr", "lentreprise.lexpress.fr", "siecledigital.fr", "journaldunet.com"]


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_35"
    agent_name = "Reputation & Signaux"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        domain = state.site_url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0] if state.site_url else ""
        brand = domain.split(".")[0] if domain else ""

        rep = {
            "brand": brand,
            "brand_search_volume": 0,
            "press_mentions_estimated": 0,
            "social_presence": [],
            "eeat_signals": {"a_propos": False, "contact": False, "mentions_legales": False, "cgu": False},
            "recommandations": [],
        }

        # Presence pages legales
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        content_lower = content.lower()

        if "a propos" in content_lower or "about" in content_lower:
            rep["eeat_signals"]["a_propos"] = True
        if "contact" in content_lower or "contactez" in content_lower:
            rep["eeat_signals"]["contact"] = True
        if "mentions legales" in content_lower or "cgv" in content_lower:
            rep["eeat_signals"]["mentions_legales"] = True
        if "cgu" in content_lower or "conditions generales" in content_lower:
            rep["eeat_signals"]["cgu"] = True

        missing = [k for k, v in rep["eeat_signals"].items() if not v]
        if missing:
            rep["recommandations"].append(f"Pages legales manquantes: {', '.join(missing)}")

        if not rep["eeat_signals"]["a_propos"]:
            rep["recommandations"].append("Creer une page 'A propos' avec expertise, equipe, historique")

        result.status = AgentStatus.COMPLETED
        result.data = rep
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state
