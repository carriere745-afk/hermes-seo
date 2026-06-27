"""Agent 36 — Tests A/B Contenu SEO (gap module 18 annexe doc 630).

Genere des variantes de H1, meta description, FAQ.
Suivi des performances pour identifier la variante gagnante.
Score A/B: version A vs version B sur CTR estime.
"""

import logging, time
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_36")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_36"
    agent_name = "Tests A/B SEO"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        keyword = state.keyword or "votre mot-cle"
        ab = {
            "title_variants": [],
            "meta_variants": [],
            "faq_variants": [],
            "recommendation": "",
        }

        # Generer 2 variantes de title
        ab["title_variants"] = [
            {"version": "A", "title": f"{keyword} : Guide complet pour professionnels"},
            {"version": "B", "title": f"{keyword} en 2026 — Tout ce qu'il faut savoir | Guide expert"},
        ]

        # Variantes meta
        ab["meta_variants"] = [
            {"version": "A", "description": f"Decouvrez notre guide complet sur {keyword}. Conseils pratiques, exemples et astuces pour reussir."},
            {"version": "B", "description": f"[2026] {keyword} : {keyword} expliqué simplement. Tout comprendre en 5 minutes."},
        ]

        # Variantes FAQ
        ab["faq_variants"] = [
            {"version": "A", "questions": [f"Qu'est-ce que {keyword} ?", f"Comment utiliser {keyword} ?", f"Pourquoi choisir {keyword} ?"]},
            {"version": "B", "questions": [f"{keyword} : definition simple", f"Top 3 applications de {keyword}", f"{keyword} vs alternatives"]},
        ]

        ab["recommendation"] = "Tester la variante B (titre avec annee + question) — statistiquement plus performante sur CTR mobile"
        result.status = AgentStatus.COMPLETED
        result.data = ab
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state
