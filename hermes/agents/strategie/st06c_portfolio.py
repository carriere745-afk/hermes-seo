"""ST06c — Portfolio Strategy.

Repartit les recommandations par categorie de portefeuille :
Acquisition, Retention, Defense, Conversion, Authority.
Skippable en mode fast. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st06c")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st06c"
    state.phase = "synthese"

    if state.mode == "fast":
        logger.info("ST06c: Skipped (mode fast)")
        state.updated_at = datetime.now()
        return state

    allocation: dict[str, float] = {
        "acquisition": 0.0,
        "retention": 0.0,
        "defense": 0.0,
        "conversion": 0.0,
        "authority": 0.0,
    }

    # Categoriser chaque recommandation
    for rec in state.recommandations:
        if rec.priorite == "KILL":
            continue
        portfolio = _categorize_recommendation(rec, state)
        rec.portfolio = portfolio
        allocation[portfolio] += 1

    # Normaliser en pourcentages
    total = sum(allocation.values()) or 1
    for k in allocation:
        allocation[k] = round(allocation[k] / total * 100, 1)

    # Recommandation de repartition ideale selon le profil
    ideal = _ideal_allocation(state.profile)

    state.portfolio_allocation = allocation
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st06c", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST06c: Portfolio — {allocation}")
    return state


def _categorize_recommendation(rec, state: StrategieState) -> str:
    """Determine la categorie de portefeuille d'une recommandation."""
    action = rec.action if hasattr(rec, 'action') else ""
    sujet = rec.sujet.lower() if hasattr(rec, 'sujet') else ""

    # Creations = acquisition
    if action in ("creer_pilier", "creer_satellite", "creer_faq", "creer_comparatif"):
        return "acquisition"

    # Enrichissement = conversion ou retention
    if action in ("enrichir_existant", "enrichir_faq"):
        if "conversion" in sujet or "achat" in sujet or "prix" in sujet:
            return "conversion"
        return "retention"

    # Fusion/suppression = defense
    if action in ("fusionner", "separer", "supprimer"):
        return "defense"

    # Optimisation = authority
    if action in ("optimiser", "consolider"):
        return "authority"

    # Defendre = defense
    if action == "defendre":
        return "defense"

    return "acquisition"


def _ideal_allocation(profile: str) -> dict[str, float]:
    """Repartition ideale selon le profil du site."""
    profiles = {
        "blog": {"acquisition": 40, "retention": 20, "defense": 10, "conversion": 10, "authority": 20},
        "ecommerce": {"acquisition": 30, "retention": 10, "defense": 10, "conversion": 40, "authority": 10},
        "saas": {"acquisition": 35, "retention": 15, "defense": 10, "conversion": 30, "authority": 10},
        "local": {"acquisition": 25, "retention": 15, "defense": 20, "conversion": 30, "authority": 10},
        "corporate": {"acquisition": 20, "retention": 10, "defense": 20, "conversion": 15, "authority": 35},
    }
    return profiles.get(profile, profiles["blog"])
