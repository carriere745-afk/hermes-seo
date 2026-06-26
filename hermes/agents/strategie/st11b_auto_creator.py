"""Agent ST11b — Auto-createur Editorial (gap P5->P1).

Quand ST11 (export/routage) identifie des recommandations ciblees vers P1,
cet agent cree automatiquement les articles correspondants via le pipeline Editorial.
Ferme le gap critique #1 du document 630 : "la strategie dit creer pilier, l'article est cree".

Skippable en fast/semi-auto. Non skippable en mode auto.
"""

import logging
import time
from datetime import datetime
from uuid import uuid4

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event, save_prediction

logger = logging.getLogger("hermes.strategie.st11b")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st11b"
    articles_crees = 0

    if state.mode == "fast" or state.mode == "semi-auto":
        logger.info("ST11b: skip — mode fast/semi-auto (creation manuelle)")
        state.updated_at = datetime.now()
        return state

    # Recommendations dirigees vers P1
    p1_targets = [r for r in state.recommandations
                  if r.pipeline_cible == "P1" and r.priorite in ("P0", "P1")]

    for rec in p1_targets[:3]:  # Max 3 articles par cycle
        try:
            # Generer l'article via P1
            result = await _create_article_via_p1(state, rec)
            if result:
                articles_crees += 1
                logger.info(f"ST11b: Article cree pour '{rec.sujet}' ({result.get('chars', 0)} chars)")
                save_prediction(
                    session_id=state.session_id, agent_id="st11b",
                    pipeline_id="strategie", action_type="article_auto_cree",
                    url=result.get("url", ""), keyword=rec.sujet,
                    predicted_traffic=rec.trafic_estime,
                    predicted_roi=rec.roi_12mois,
                )
        except Exception as e:
            logger.warning(f"ST11b: echec creation article '{rec.sujet}': {e}")

    state.session_data = {
        **(state.session_data or {}),
        "articles_auto_crees": articles_crees,
    }
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="st11b", pipeline_id="strategie",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)

    if articles_crees:
        logger.info(f"ST11b: {articles_crees} articles crees automatiquement via P1")
    return state


async def _create_article_via_p1(state, rec) -> dict | None:
    """Cree un article via le pipeline Editorial (P1) pour une recommandation."""
    try:
        from hermes.models.session import SessionState, SessionConfig
        from hermes.models.common import QualityMode
        from hermes.agents import AGENT_REGISTRY
        from hermes.core.workflow import AGENT_ORDER

        p1_state = SessionState()
        p1_state.keyword = rec.sujet
        p1_state.site_url = state.site_url
        p1_state.config = SessionConfig(
            mode=QualityMode.STANDARD,
            secteur=state.profile or "blog",
            objectif=f"Creer un {rec.action} sur le sujet '{rec.sujet}' "
                     f"pour le site {state.domain or state.site_url}",
        )

        # Executer le pipeline Editorial
        for agent_id in AGENT_ORDER:
            if agent_id in AGENT_REGISTRY:
                p1_state.current_agent_id = agent_id
                try:
                    p1_state = await AGENT_REGISTRY[agent_id](p1_state)
                except Exception:
                    continue
            if agent_id == "agent_09" and p1_state.brouillon_html:
                break

        content = ""
        if p1_state.brouillon_html:
            content = (p1_state.brouillon_html.html
                      if hasattr(p1_state.brouillon_html, 'html')
                      else str(p1_state.brouillon_html))

        if content and len(content) > 500:
            return {"url": f"/{rec.sujet.replace(' ', '-')[:50]}",
                    "chars": len(content), "content": content[:5000]}
    except Exception as e:
        logger.warning(f"P1 creation failed: {e}")
    return None
