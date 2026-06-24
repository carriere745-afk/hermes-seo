"""ST09 — Revue Humaine.

Flag les sujets necessitant une relecture humaine :
YMYL, controverses, legal, secteurs reglementes.
Skippable en mode fast (sauf mode compliance). $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st09")

# Mots-cles sensibles YMYL (Your Money Your Life)
YMYL_PATTERNS = [
    "sante", "medecin", "traitement", "diagnostic", "symptome", "maladie",
    "financ", "investir", "credit", "pret", "assurance", "fiscal", "impot",
    "juridique", "avocat", "droit", "loi", "legal", "tribunal",
    "securite", "danger", "risque", "accident",
    "enfant", "bebe", "nourrisson", "pediatrie",
    "medicament", "pharmacie", "ordonnance", "posologie",
]

CONTROVERSE_PATTERNS = [
    "polemique", "controverse", "scandale", "accusation",
    "politique", "religion", "avortement", "euthanasie",
    "crypto", "bitcoin", "gambling", "casino", "pari",
]

LEGAL_PATTERNS = [
    "mentions legales", "cgv", "conditions generales", "politique de confidentialite",
    "rgpd", "cookies", "consentement", "donnees personnelles",
]


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st09"
    state.phase = "synthese"

    # Skip en mode fast sauf si compliance
    if state.mode == "fast" and state.mode != "compliance":
        logger.info("ST09: Skipped (mode fast)")
        state.updated_at = datetime.now()
        return state

    flags: list[dict] = []

    for rec in state.recommandations:
        sujet_lower = rec.sujet.lower()
        keywords = " ".join(rec.keywords).lower() if rec.keywords else ""

        ymyl_matches = [p for p in YMYL_PATTERNS if p in sujet_lower or p in keywords]
        controverse_matches = [p for p in CONTROVERSE_PATTERNS if p in sujet_lower or p in keywords]
        legal_matches = [p for p in LEGAL_PATTERNS if p in sujet_lower or p in keywords]

        if ymyl_matches or controverse_matches or legal_matches:
            flag = {
                "sujet": rec.sujet,
                "keywords": rec.keywords,
                "ymyl": len(ymyl_matches) > 0,
                "ymyl_patterns": ymyl_matches,
                "controverse": len(controverse_matches) > 0,
                "controverse_patterns": controverse_matches,
                "legal": len(legal_matches) > 0,
                "legal_patterns": legal_matches,
                "requires_human_review": True,
                "review_priority": "high" if ymyl_matches else "medium",
                "recommandation": (
                    "Ne pas publier sans relecture par un expert du domaine"
                    if ymyl_matches
                    else "Relecture recommandee avant publication"
                ),
            }
            flags.append(flag)

    state.revue_humaine_flags = flags
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st09", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST09: {len(flags)} sujets flagges pour relecture humaine")
    return state
