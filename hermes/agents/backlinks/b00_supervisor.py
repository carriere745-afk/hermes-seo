"""B00 — Superviseur Backlinks.

Startup check : verifie DataForSEO, GSC, Bing Webmaster, init DB.
Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from urllib.parse import urlparse

from hermes.models.backlinks import BacklinksState
from hermes.core.backlinks_db import init_db
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b00")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b00"
    state.phase = "startup"

    # 1. Validation URL
    if state.site_url:
        if not state.site_url.startswith("http"):
            state.site_url = f"https://{state.site_url}"
        parsed = urlparse(state.site_url)
        state.domain = parsed.netloc.lower().replace("www.", "")

    # 2. Session ID
    if not state.session_id:
        state.session_id = f"bl-{state.domain or 'no-url'}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # 3. Verifier APIs
    state.apis_disponibles = {}

    # DataForSEO
    try:
        from hermes.connectors.dataforseo_connector import dataforseo
        state.apis_disponibles["dataforseo"] = dataforseo.is_configured
    except Exception:
        state.apis_disponibles["dataforseo"] = False

    # GSC
    try:
        from hermes.connectors.gsc_connector import gsc
        state.apis_disponibles["gsc"] = gsc.is_configured
    except Exception:
        state.apis_disponibles["gsc"] = False

    # Bing Webmaster (always available for basic use)
    state.apis_disponibles["bing"] = False  # À intégrer
    state.apis_disponibles["indexnow"] = True  # Gratuit, pas de clé

    if not any(state.apis_disponibles.values()):
        logger.warning("B00: Aucune API active. L'audit backlinks sera limite aux donnees statiques.")
        state.errors.append("Aucune API backlinks configuree.")

    # 4. Init DB
    try:
        init_db()
        logger.info("B00: Backlinks DB initialisee")
    except Exception as e:
        logger.error(f"B00: DB init failed: {e}")
        state.errors.append(f"DB init: {e}")

    # 5. Config par defaut
    if not state.competitors:
        logger.info("B00: Aucun concurrent specifie. Le gap analysis sera limite.")

    state.startup_ok = True
    state.status = "running"
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="b00", pipeline_id="backlinks",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
    )

    logger.info(f"B00: Session {state.session_id} — DFSEO={state.apis_disponibles.get('dataforseo')}, "
                f"GSC={state.apis_disponibles.get('gsc')}")
    return state
