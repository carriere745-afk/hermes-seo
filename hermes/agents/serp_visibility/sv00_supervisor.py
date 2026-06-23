"""S00 — Superviseur SERP.

Initialise et supervise chaque cycle du Pipeline 4.
- Charge la configuration site (mots-cles, concurrents, seuils)
- Verifie les cles API (GSC, DataForSEO)
- Initialise la base SQLite
- Lock fichier (une seule instance a la fois)
- Non skippable.

$0 — pas de LLM.
"""

import logging
import os
from datetime import datetime
from urllib.parse import urlparse

from hermes.models.serp_visibility import SerpVisibilityState

logger = logging.getLogger("hermes.serp.sv00")

LOCK_FILE = "data/serp_visibility.lock"


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv00"

    # 1. Validation URL
    if not state.site_url:
        state.status = "error"
        logger.error("S00: site_url manquant")
        return state
    if not state.site_url.startswith("http"):
        state.site_url = f"https://{state.site_url}"

    parsed = urlparse(state.site_url)
    state.domain = parsed.netloc.lower().replace("www.", "")

    # 2. Session ID
    if not state.session_id:
        state.session_id = f"serp-{state.domain}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # 3. Verifier GSC
    gsc_ok = False
    try:
        from hermes.connectors.gsc_connector import gsc
        gsc_ok = gsc.is_configured
    except Exception:
        pass

    if not gsc_ok:
        logger.warning("S00: GSC non connecte — seules les APIs payantes seront utilisees")

    # 4. Initialiser SQLite
    try:
        from hermes.core.serp_db import init_db
        init_db()
        logger.info("S00: SQLite initialisee")
    except Exception as e:
        logger.error(f"S00: SQLite init failed ({e})")

    # 5. Verifier lock fichier (une seule instance a la fois)
    if os.path.exists(LOCK_FILE):
        mtime = os.path.getmtime(LOCK_FILE)
        age_hours = (datetime.now().timestamp() - mtime) / 3600
        if age_hours < 12:
            logger.warning("S00: une instance est deja en cours (lock < 12h). Skip.")
            state.status = "locked"
            return state
        else:
            logger.warning("S00: vieux lock (> 12h) — on force")
            os.remove(LOCK_FILE)

    # 6. Config par defaut
    if not state.alert_thresholds:
        state.alert_thresholds = {
            "chute_critique": 10,
            "chute_importante": 5,
            "gain_important": 5,
        }
    if not state.tracking_devices:
        state.tracking_devices = ["mobile"]

    state.status = "initialized"
    state.cycle_count += 1
    state.updated_at = datetime.now()

    # Creer le lock
    try:
        os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
        with open(LOCK_FILE, "w") as f:
            f.write(state.session_id)
    except Exception:
        pass

    logger.info(f"S00: cycle {state.cycle_count} initialise — {len(state.keywords)} keywords, GSC={'OK' if gsc_ok else 'non connecte'}")
    return state
