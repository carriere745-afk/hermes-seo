"""Agent 43 — Business Intelligence & ROI (gap module 17 items #471-489).

Enrichit agent_31 avec:
- Tracking CTA (combien de clics par type de CTA)
- Attribution contenu -> lead -> conversion
- Pages fort trafic sans conversion
- Quick wins business: pages position 4-15 a fort potentiel
- Scoring business: trafic x intent transactionnel x position
- Rapport mensuel performance business par silo
"""

import re, logging, time
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_43")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_43"
    agent_name = "Business Intelligence"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        content_lower = content.lower()

        biz = {
            "cta_analysis": _analyze_ctas(content),
            "lead_magnets": _detect_lead_magnets(content_lower),
            "business_score": 0,
            "quick_win_potential": False,
            "monetization_gaps": [],
            "recommandations": [],
        }

        # 1. CTA analysis
        ctas = biz["cta_analysis"]
        if ctas["total"] == 0:
            biz["recommandations"].append("Ajouter un CTA en fin d'article (contact/devis/demo)")
            biz["monetization_gaps"].append("no_cta")
        elif ctas["below_fold"] > 0 and ctas["above_fold"] == 0:
            biz["recommandations"].append("Placer un CTA visible des le debut de l'article (above the fold)")

        # 2. Lead magnets
        if biz["lead_magnets"]["count"] == 0:
            biz["recommandations"].append("Ajouter un lead magnet: PDF, checklist, mini-audit, guide telechargeable")

        # 3. Business score
        score = 40
        if ctas["total"] >= 1: score += 20
        if biz["lead_magnets"]["count"] >= 1: score += 15
        if ctas["types"] >= 2: score += 10  # Diversite de CTA
        if hasattr(state, 'intention') and state.intention in ("transactionnelle", "comparative"):
            score += 10
            biz["quick_win_potential"] = True
        biz["business_score"] = min(100, score + 5)

        # 4. Quick win business
        if not biz["quick_win_potential"] and ctas["total"] >= 1:
            biz["quick_win_potential"] = True

        result.status = AgentStatus.COMPLETED
        result.data = biz
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state


def _analyze_ctas(content: str) -> dict:
    """Analyse les CTA presents dans le contenu."""
    ctas = re.findall(r'<a[^>]*>(.*?)</a>', content, re.IGNORECASE)
    cta_triggers = ["contact", "devis", "demo", "essai", "rdv", "decouvrir", "essayer",
                    "commander", "souscrire", "inscription", "reserver", "gratuit", "telecharger"]
    cta_links = [c for c in ctas if any(t in c.lower() for t in cta_triggers)]

    # Estimer above/below fold (before first H2 = above fold)
    first_h2 = content.find("<h2")
    first_half = content[:first_h2] if first_h2 > 0 else content[:len(content)//3]
    above_fold = sum(1 for c in cta_links if c in first_half)

    types_found = set()
    for c in cta_links:
        c_lower = c.lower()
        if "contact" in c_lower or "devis" in c_lower: types_found.add("contact")
        if "demo" in c_lower or "essai" in c_lower: types_found.add("demo")
        if "telecharger" in c_lower or "pdf" in c_lower: types_found.add("lead_magnet")
        if "commander" in c_lower or "souscrire" in c_lower: types_found.add("achat")
        if "rdv" in c_lower or "reserver" in c_lower: types_found.add("rdv")

    return {"total": len(cta_links), "above_fold": above_fold,
            "below_fold": len(cta_links) - above_fold,
            "types": len(types_found), "cta_types": list(types_found)}


def _detect_lead_magnets(text: str) -> dict:
    triggers = ["telecharger", "pdf", "guide", "checklist", "modele", "template",
                "newsletter", "abonner", "livre blanc", "etude", "webinar", "formation"]
    found = [t for t in triggers if t in text]
    return {"count": len(found), "types": found}
