"""B17 — Media Relationship Score (V3).

Evalue la qualite de la relation avec chaque media/contact
a partir de l'historique du CRM (B07).
Skippable (V3). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from hermes.models.backlinks import BacklinksState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b17")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b17"
    state.phase = "analyse"

    relationships = []
    for camp in state.campaigns:
        if not camp.domain:
            continue

        # Score relationnel base sur l'historique CRM
        total_contacts = camp.followup_count + 1
        total_responses = 1 if camp.status != "prospect" else 0
        total_publications = 1 if camp.link_acquired else 0

        response_rate = total_responses / max(total_contacts, 1)
        publication_rate = total_publications / max(total_contacts, 1)

        score = int(
            response_rate * 0.30 * 100 +
            publication_rate * 0.25 * 100 +
            0.20 * 50 +  # delai moyen estime
            0.15 * 40 +  # qualite estimee
            0.10 * 60    # frequence estimee
        )

        relationships.append({
            "media_domain": camp.domain,
            "contact_email": camp.contact_email,
            "contact_name": camp.contact_name,
            "total_contacts": total_contacts,
            "total_responses": total_responses,
            "total_publications": total_publications,
            "relationship_score": min(100, score),
        })

    state.media_relationships = relationships
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="b17", pipeline_id="backlinks",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)

    logger.info(f"B17: Media Relationship — {len(relationships)} medias scores")
    return state
