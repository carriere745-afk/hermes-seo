"""B15 — Link Portfolio Optimizer (V3).

Optimise le portefeuille de liens comme un portefeuille financier.
Garantit la diversité des sources d'autorité.
Skippable (V3). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from hermes.models.backlinks import BacklinksState, PortfolioSnapshot
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b15")

TARGET_MIX = {
    "blog": {"media_national": 25, "media_sectoriel": 20, "blogs_experts": 15, "annuaires": 10,
             "associations": 10, "partenariats": 10, "podcasts": 5, "communautes": 5},
    "ecommerce": {"media_national": 20, "media_sectoriel": 25, "blogs_experts": 15, "annuaires": 10,
                  "associations": 5, "partenariats": 15, "podcasts": 5, "communautes": 5},
    "agressif": {"media_national": 35, "media_sectoriel": 20, "blogs_experts": 15, "annuaires": 5,
                 "associations": 5, "partenariats": 10, "podcasts": 5, "communautes": 5},
    "defensif": {"media_national": 20, "media_sectoriel": 25, "blogs_experts": 15, "annuaires": 10,
                 "associations": 15, "partenariats": 10, "podcasts": 5, "communautes": 0},
    "local": {"media_national": 10, "media_sectoriel": 15, "blogs_experts": 10, "annuaires": 20,
              "associations": 20, "partenariats": 15, "podcasts": 5, "communautes": 5},
}


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b15"
    state.phase = "analyse"

    target = TARGET_MIX.get(state.profile, TARGET_MIX["blog"])

    # Compter les types de domaines actuels
    current_mix = {"media_national": 0, "media_sectoriel": 0, "blogs_experts": 0,
                   "annuaires": 0, "associations": 0, "partenariats": 0,
                   "podcasts": 0, "communautes": 0}
    total = max(len(state.referring_domains), 1)
    for d in state.referring_domains:
        t = d.domain_type
        if "media_national" in t:
            current_mix["media_national"] += 1
        elif "media_sectoriel" in t:
            current_mix["media_sectoriel"] += 1
        elif "blog" in t:
            current_mix["blogs_experts"] += 1
        elif "annuaire" in t:
            current_mix["annuaires"] += 1
        elif "association" in t:
            current_mix["associations"] += 1
        elif "partenariat" in t:
            current_mix["partenariats"] += 1
        elif "podcast" in t:
            current_mix["podcasts"] += 1
        elif "forum" in t or "communaute" in t:
            current_mix["communautes"] += 1

    # Normaliser
    for k in current_mix:
        current_mix[k] = round(current_mix[k] / total * 100, 1)

    snapshot = PortfolioSnapshot(
        media_national_ratio=current_mix["media_national"],
        media_sectoriel_ratio=current_mix["media_sectoriel"],
        blogs_experts_ratio=current_mix["blogs_experts"],
        annuaires_ratio=current_mix["annuaires"],
        associations_ratio=current_mix["associations"],
        partenariats_ratio=current_mix["partenariats"],
        podcasts_ratio=current_mix["podcasts"],
        communautes_ratio=current_mix["communautes"],
        target_mix=target,
    )

    state.portfolio_snapshot = snapshot
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="b15", pipeline_id="backlinks",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)

    logger.info(f"B15: Portfolio Optimizer — snapshot captured")
    return state
