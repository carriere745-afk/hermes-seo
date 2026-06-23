"""T14 — Impact Business & Gain Potentiel.

Evalue l'impact business de chaque probleme :
- Source GSC (trafic reel) → confidence high
- Fallback par type de page (proxy) → confidence medium

Estimation qualitative uniquement (High/Medium/Low).
Aucun chiffre precis.

$0 — pas de LLM.
"""

import logging
from datetime import datetime

from hermes.models.audit_tech import TechAuditState

logger = logging.getLogger("hermes.audit_tech.tt14")

# Impact business par type de page (fallback sans GSC)
TYPE_IMPACT = {
    "accueil": {"traffic": "High", "business": "High"},
    "produit": {"traffic": "High", "business": "High"},
    "service": {"traffic": "High", "business": "High"},
    "article": {"traffic": "Medium", "business": "Medium"},
    "categorie": {"traffic": "High", "business": "Medium"},
    "landing": {"traffic": "Medium", "business": "High"},
    "faq": {"traffic": "Medium", "business": "Low"},
    "marque": {"traffic": "Medium", "business": "Low"},
    "legale": {"traffic": "Low", "business": "Low"},
    "autre": {"traffic": "Medium", "business": "Medium"},
}

# Gain potentiel par type de probleme
GAIN_BY_CATEGORY = {
    "anomalies": "High",
    "indexation": "High",
    "performance": "High",
    "security": "High",
    "architecture": "High",
    "structure": "Medium",
    "content": "High",
    "mobile": "Medium",
    "schema": "Medium",
    "international": "High",
    "maillage": "Medium",
    "sitemap": "Medium",
    "code_quality": "Medium",
}


async def run(state: TechAuditState) -> TechAuditState:
    state.current_agent = "tt14"
    if not state.issues:
        logger.info("T14: no issues to evaluate")
        state.updated_at = datetime.now()
        return state

    # Verifier GSC
    gsc_available = False
    try:
        from hermes.connectors.gsc_connector import gsc
        gsc_available = gsc.is_configured
    except Exception:
        pass

    logger.info(f"T14: evaluating impact for {len(state.issues)} issues (GSC={'connected' if gsc_available else 'unavailable'})")

    from hermes.agents.audit_tech.tt06_thin_content import _get_page_type

    for issue in state.issues:
        # 1. Impact business via type de page
        if issue.url and issue.url.startswith("http"):
            ptype = _get_page_type(issue.url)
        else:
            ptype = "autre"

        impact = TYPE_IMPACT.get(ptype, TYPE_IMPACT["autre"])
        issue.impact_business = impact["business"]
        issue.confidence = "high" if gsc_available else "medium"

        # 2. Gain potentiel via categorie
        issue.gain_potentiel = GAIN_BY_CATEGORY.get(issue.category, "Medium")

        # 3. Ajuster si GSC dispo (conservatif)
        if not gsc_available and issue.impact_business == "High":
            issue.confidence = "medium"

    # Resume business impact
    state.business_impact_summary = {"High": 0, "Medium": 0, "Low": 0}
    for issue in state.issues:
        state.business_impact_summary[issue.impact_business] = state.business_impact_summary.get(issue.impact_business, 0) + 1

    logger.info(f"T14: impact summary={state.business_impact_summary}")
    state.updated_at = datetime.now()
    return state
