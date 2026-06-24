"""ST00 — Superviseur Strategie.

Startup check : verifie P2/P3/P4, initialise la DB, configure la session.
Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import init_db, log_event

logger = logging.getLogger("hermes.strategie.st00")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st00"
    state.phase = "startup"

    # 1. Validation URL
    if state.site_url:
        if not state.site_url.startswith("http"):
            state.site_url = f"https://{state.site_url}"
        parsed = urlparse(state.site_url)
        state.domain = parsed.netloc.lower().replace("www.", "")

    # 2. Session ID
    if not state.session_id:
        state.session_id = f"strat-{state.domain or 'no-url'}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # 3. Verifier pipelines disponibles
    state.pipelines_disponibles = {}
    # P2 — Audit de Contenu
    p2_db = Path("data/audit_contenu.db")
    state.pipelines_disponibles["p2"] = p2_db.exists()
    # P3 — Audit Technique
    p3_db = Path("data/audit_technique.db")
    state.pipelines_disponibles["p3"] = p3_db.exists()
    # P4 — SERP
    p4_db = Path("data/serp_visibility.db")
    state.pipelines_disponibles["p4"] = p4_db.exists()

    p2p3p4 = state.pipelines_disponibles
    available = [k for k, v in p2p3p4.items() if v]
    logger.info(f"ST00: Pipelines disponibles: {available}")

    if not available:
        logger.warning("ST00: Aucun pipeline upstream disponible. Mode degrade — analyses seront basees sur donnees mock/statiques.")
        state.errors.append("Aucun pipeline upstream (P2/P3/P4) disponible. Analyses basees sur donnees statiques.")

    # 4. GA4
    state.ga4_configure = False
    try:
        from hermes.config import _cfg
        if _cfg._resolve("GA4_PROPERTY_ID"):
            state.ga4_configure = True
    except Exception:
        pass

    # 5. Init DB
    try:
        init_db()
        logger.info("ST00: Strategie DB initialisee")
    except Exception as e:
        logger.error(f"ST00: DB init failed: {e}")
        state.errors.append(f"DB init: {e}")

    # 6. Mode fast adjustments
    if state.mode == "fast":
        logger.info("ST00: Mode fast — agents lourds (ST05b, ST06b, ST06c, ST09) seront skippes")

    # 7. Default config
    if not state.priorisation_config:
        state.priorisation_config = {
            "poids_business": 0.35,
            "poids_faisabilite": 0.20,
            "poids_effort": 0.15,
            "poids_volume": 0.15,
            "poids_opportunite": 0.10,
            "poids_urgence": 0.05,
        }

    state.startup_ok = True
    state.status = "running"
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st00", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST00: Session {state.session_id} initialisee — mode={state.mode}, "
                f"p2={p2p3p4['p2']}, p3={p2p3p4['p3']}, p4={p2p3p4['p4']}, ga4={state.ga4_configure}")
    return state
