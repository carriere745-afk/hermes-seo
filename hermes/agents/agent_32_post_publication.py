"""Agent 32 — Post-Publication Monitoring (gap module 14 du doc 630).

File de revision editoriale : statut par URL, alerte peremption,
revision declenchee par Core Update, rapport mensuel articles revises.
"""

import logging, time
from datetime import datetime, timedelta

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_32")

PEREMPTION_DELAYS = {"news": 60, "analyse": 90, "pilier": 180, "comparatif": 90, "fiche_outil": 90, "page_service": 180}


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_32"
    agent_name = "Suivi Post-Publication"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        monitoring = {
            "content_age_days": 0,
            "peremption_days": 0,
            "needs_revision": False,
            "revision_reason": "",
            "last_revision_date": None,
            "revision_priority": "P3",
            "alerts": [],
        }

        # Age du contenu
        if hasattr(state, 'created_at') and state.created_at:
            age = (datetime.now() - state.created_at).days
            monitoring["content_age_days"] = age

            type_page = state.type_page or "article"
            max_age = PEREMPTION_DELAYS.get(type_page, 180)
            monitoring["peremption_days"] = max(0, max_age - age)

            if age > max_age:
                monitoring["needs_revision"] = True
                monitoring["revision_reason"] = f"Contenu age de {age} jours (seuil {type_page}: {max_age}j)"
                monitoring["revision_priority"] = "P1" if age > max_age * 1.5 else "P2"

        # Alerte si positions en baisse (depuis P4)
        if hasattr(state, 'agent_results'):
            p26 = state.agent_results.get("agent_26")
            if p26 and p26.status == AgentStatus.COMPLETED and p26.data:
                gsc_data = p26.data if isinstance(p26.data, dict) else {}
                if gsc_data.get("traffic_drop", 0) > 20:
                    monitoring["alerts"].append(f"Chute trafic >20% detectee")

        result.status = AgentStatus.COMPLETED
        result.data = monitoring
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state
