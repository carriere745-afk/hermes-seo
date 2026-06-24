"""B07 — CRM & Pilotage Campagnes.

Pipeline de suivi des campagnes de netlinking :
- Prospection → Contacte → Relance → En cours → Accepte → Publie
- Suivi des relances, calendrier, notes
- Integration email en V1.5

Non skippable (MVP). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime, timedelta
from uuid import uuid4

from hermes.models.backlinks import BacklinksState, CampaignContact
from hermes.core.backlinks_db import (
    insert_campaign, get_campaigns, get_followups_today,
    get_opportunities,
)
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.backlinks.b07")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b07"
    state.phase = "execution"

    campaigns: list[CampaignContact] = []
    today = datetime.now()

    # 1. Charger les opportunites existantes
    opps = get_opportunities(status="prospect")

    # 2. Creer des campagnes pour les opportunites non encore suivies
    existing_campaigns = {c.domain: c for c in state.campaigns}

    for opp in opps[:50]:
        domain = opp.get("domain", "")
        if domain in existing_campaigns:
            campaigns.append(existing_campaigns[domain])
            continue

        # Creer une nouvelle campagne
        campaign = CampaignContact(
            opportunity_id=opp.get("id", ""),
            domain=domain,
            contact_name="",
            contact_email="",
            contact_role="",
            status="prospect",
            next_followup_date=today + timedelta(days=3),
            followup_count=0,
            notes=opp.get("description", ""),
            cost_engaged=opp.get("cost_estime", 0),
        )
        campaigns.append(campaign)

        # Persister
        insert_campaign({
            "id": campaign.id,
            "opportunity_id": campaign.opportunity_id,
            "domain": campaign.domain,
            "contact_name": campaign.contact_name,
            "contact_email": campaign.contact_email,
            "contact_role": campaign.contact_role,
            "status": campaign.status,
            "next_followup_date": campaign.next_followup_date.isoformat() if campaign.next_followup_date else None,
            "followup_count": campaign.followup_count,
            "notes": campaign.notes,
            "cost_engaged": campaign.cost_engaged,
            "session_id": state.session_id,
        })

    # 3. Verifier les relances du jour
    followups_today = get_followups_today()
    if followups_today:
        logger.info(f"B07: {len(followups_today)} relances prevues aujourd'hui")

    # 4. Mettre a jour les opportunites avec les statuts CRM
    for opp in opps:
        for camp in campaigns:
            if camp.opportunity_id == opp.get("id"):
                opp["status"] = camp.status
                break

    state.campaigns = campaigns
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="b07", pipeline_id="backlinks",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
    )

    n_active = sum(1 for c in campaigns if c.status not in ("publie", "refuse", "abandonne"))
    logger.info(f"B07: {len(campaigns)} campagnes CRM — {n_active} actives, {len(followups_today)} relances du jour")
    return state
