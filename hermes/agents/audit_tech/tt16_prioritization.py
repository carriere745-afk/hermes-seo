"""T16 — Priorisation (poids configurables par profil client).

Classe les problemes par ordre de priorite selon :
- Impact SEO (configurable)
- Impact Business (depuis T14)
- Effort (inverse)
- Conformite (pour les sites institutionnels)

Poids par defaut selon le profil client.
Formule: Score = SEO × w_seo + Business × w_business + Conformite × w_conv - Effort × w_effort

$0 — deterministe.
"""

import logging
from datetime import datetime

from hermes.models.audit_tech import TechAuditState

logger = logging.getLogger("hermes.audit_tech.tt16")

# Poids par profil client
PROFILE_WEIGHTS = {
    "ecommerce": {"seo": 0.40, "business": 0.50, "effort": 0.10, "conformite": 0.00},
    "blog": {"seo": 0.60, "business": 0.30, "effort": 0.10, "conformite": 0.00},
    "institutionnel": {"seo": 0.30, "business": 0.20, "effort": 0.20, "conformite": 0.30},
    "agence": {"seo": 0.40, "business": 0.30, "effort": 0.20, "conformite": 0.10},
    "saas": {"seo": 0.35, "business": 0.45, "effort": 0.15, "conformite": 0.05},
}

SEVERITY_SCORE = {"critical": 100, "high": 70, "medium": 40, "low": 15, "info": 0}
IMPACT_SCORE = {"High": 100, "Medium": 50, "Low": 10}
GAIN_SCORE = {"High": 100, "Medium": 50, "Low": 10}
EFFORT_SCORE = {"5 min": 5, "15 min": 15, "30 min": 30, "1h": 60, "2h": 120, "Varie": 60}


def _estimate_effort_minutes(effort_str: str) -> int:
    for key, val in EFFORT_SCORE.items():
        if key in effort_str:
            return val
    return 60


async def run(state: TechAuditState) -> TechAuditState:
    state.current_agent = "tt16"
    if not state.issues:
        return state

    weights = PROFILE_WEIGHTS.get(state.profile, PROFILE_WEIGHTS["blog"])
    logger.info(f"T16: prioritizing {len(state.issues)} issues (profile={state.profile})")

    for issue in state.issues:
        seo = SEVERITY_SCORE.get(issue.severity, 40)
        biz = IMPACT_SCORE.get(issue.impact_business, 50)
        gain = GAIN_SCORE.get(issue.gain_potentiel, 50)
        effort = _estimate_effort_minutes(issue.effort) / 2  # normaliser

        score = (
            seo * weights["seo"]
            + biz * weights["business"]
            + gain * 0.1  # gain dilue
            - effort * weights["effort"]
        )

        # Assigner priorite
        if score >= 75:
            issue.priority = "P0"
        elif score >= 50:
            issue.priority = "P1"
        elif score >= 30:
            issue.priority = "P2"
        else:
            issue.priority = "P3"

    # Trier par priorite
    state.issues.sort(key=lambda i: (
        {"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(i.priority, 9),
        -(SEVERITY_SCORE.get(i.severity, 0))
    ))

    p0 = sum(1 for i in state.issues if i.priority == "P0")
    p1 = sum(1 for i in state.issues if i.priority == "P1")
    logger.info(f"T16: prioritized — P0={p0}, P1={p1}, P2={sum(1 for i in state.issues if i.priority=='P2')}, P3={sum(1 for i in state.issues if i.priority=='P3')}")

    state.updated_at = datetime.now()
    return state
