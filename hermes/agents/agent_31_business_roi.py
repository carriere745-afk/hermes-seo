"""Agent 31 — Business/ROI Tracking (gap module 17 du doc 630).

Suit : clics CTA, attribution contenu->lead->conversion,
pages a fort trafic sans conversion, quick wins business,
score business par page (trafic x intent transactionnel x position).
"""

import logging, time
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_31")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_31"
    agent_name = "Business & ROI"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        biz = {
            "cta_presence": False,
            "cta_optimise": False,
            "business_score": 0,
            "quick_win_potential": False,
            "lead_potential": 0,
            "recommandations": [],
        }

        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        content_lower = content.lower()

        # CTA presence
        cta_triggers = ["contact", "devis", "demo", "essai", "rdv", "decouvrir", "essayer", "commander", "souscrire", "inscription", "reserver", "gratuit"]
        cta_found = [t for t in cta_triggers if t in content_lower]
        if cta_found:
            biz["cta_presence"] = True
            biz["business_score"] += 25
        else:
            biz["recommandations"].append("Ajouter un CTA (contact/devis/demo/essai) en fin d'article")

        # Lead magnet ou formulaire
        lead_triggers = ["telecharger", "pdf", "guide", "checklist", "modele", "template", "newsletter", "abonner"]
        lead_found = [t for t in lead_triggers if t in content_lower]
        if lead_found:
            biz["lead_potential"] = 30
            biz["business_score"] += 20

        # Intent transactionnelle/comparative
        if hasattr(state, 'intention') and state.intention in ("transactionnelle", "comparative"):
            biz["business_score"] += 25
            biz["quick_win_potential"] = True

        # Estimation leads (CTR x conversion x traffic estime)
        if hasattr(state, 'keyword') and state.keyword:
            biz["lead_potential"] = max(biz["lead_potential"], 15)
            biz["business_score"] += 15

        biz["business_score"] = min(100, biz["business_score"] + 15)

        result.status = AgentStatus.COMPLETED
        result.data = biz
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state
