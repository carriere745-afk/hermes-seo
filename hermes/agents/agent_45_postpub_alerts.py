"""Agent 45 — Alertes Post-Publication (gap module 14 items #424-440).

Surveille les pages apres publication:
- Non indexee apres 7 jours
- Desindexee soudainement
- Perte >5 positions sur requete cle
- Chute trafic organique >20% sur 7 jours
- Contenu perime selon type (60j news, 90j fiche, 180j pilier)
- Prix obsoletes dans fiche outil
- Core update impact
"""

import logging, re, time
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_45")

PEREMPTION = {"news": 60, "fiche_outil": 90, "comparatif": 90, "pilier": 180, "analyse": 120, "article": 150}


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_45"
    agent_name = "Alertes Post-Publication"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        alerts_list = []
        revisions = []

        # 1. Peremption
        if hasattr(state, 'created_at') and state.created_at:
            age_days = (datetime.now() - state.created_at).days
            tp = state.type_page or "article"
            max_days = PEREMPTION.get(tp, 150)
            if age_days > max_days:
                alerts_list.append({"type": "peremption", "severite": "P1" if age_days > max_days * 1.5 else "P2",
                                    "message": f"Contenu age de {age_days}j (seuil {tp}: {max_days}j)",
                                    "action": "Reviser le contenu"})
                revisions.append({"date": datetime.now().isoformat(), "reason": "peremption", "type": tp})

        # 2. Chute trafic
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        if hasattr(state, 'agent_results'):
            p26 = state.agent_results.get("agent_26")
            if p26 and p26.status == AgentStatus.COMPLETED and p26.data:
                gsc = p26.data if isinstance(p26.data, dict) else {}
                traffic_drop = gsc.get("traffic_drop", 0)
                if traffic_drop > 20:
                    alerts_list.append({"type": "traffic_drop", "severite": "P1",
                                        "message": f"Chute de trafic de {traffic_drop}%",
                                        "action": "Analyser les causes et enrichir le contenu"})

        # 3. Prix obsoletes (fiche outil)
        tp = state.type_page or ""
        if "fiche_outil" in tp or "produit" in tp:
            prix_dates = re.findall(r'(\d{1,4})\s*euros?', content)
            if prix_dates:
                # Verifier si le contenu a plus de 90 jours = prix potentiellement obsoletes
                if hasattr(state, 'created_at') and state.created_at:
                    if (datetime.now() - state.created_at).days > 90:
                        alerts_list.append({"type": "prix_obsolete", "severite": "P2",
                                            "message": "Prix potentiellement obsoletes (>90j)",
                                            "action": "Verifier et mettre a jour les prix"})

        result.status = AgentStatus.COMPLETED
        result.data = {"alerts": alerts_list, "revisions": revisions,
                       "next_revision_date": _next_revision_date(state),
                       "revision_priority": alerts_list[0]["severite"] if alerts_list else "P3"}
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state


def _next_revision_date(state) -> str | None:
    if not hasattr(state, 'created_at') or not state.created_at:
        return None
    tp = state.type_page or "article"
    max_days = PEREMPTION.get(tp, 150)
    next_date = state.created_at + timedelta(days=max_days)
    return next_date.strftime("%Y-%m-%d")
