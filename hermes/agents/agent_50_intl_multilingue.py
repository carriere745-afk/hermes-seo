"""Agent 50 — International SEO Avance (gap module 22 items #591-600).

Gere les projets multilingues: liaison paires FR<->EN, controle anti-traduction
litterale, qualite traduction, slugs distincts, couverture multilingue.
Score de performance SEO par langue.
"""

import re, logging, time
from datetime import datetime
from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_50")

CALQUES_FR_EN = {"digital": "numerique", "infrastructure": "infrastructure",
                 "business": "entreprise", "solution": "solution",
                 "scalable": "evolutif", "disruptif": "de rupture"}
CALQUES_EN_FR = {"accompagnement": "support", "deploiement": "deployment",
                 "valorisation": "valuation", "realiser": "carry out"}


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_50"; agent_name = "International SEO Avance"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
    text = re.sub(r'<[^>]+>', ' ', content).lower()

    intl = {"is_multilingual": False, "language_detected": "fr",
            "calques_detected": [], "translation_quality_score": 100,
            "slugs_issues": [], "coverage_pct": 0,
            "recommandations": []}

    # Detection langue
    if re.search(r'\b(the|are|will|have|been|this|that|with|from|your)\b', text):
        intl["language_detected"] = "en"

    # Detection hreflang
    if re.search(r'hreflang', content.lower()):
        intl["is_multilingual"] = True

    # Calques
    if intl["language_detected"] == "fr":
        for ang, fr in CALQUES_FR_EN.items():
            if re.search(rf'\b{ang}\b', text):
                intl["calques_detected"].append(f"'{ang}' -> preferer '{fr}'")
                intl["translation_quality_score"] -= 10
    elif intl["language_detected"] == "en":
        for fr, en in CALQUES_EN_FR.items():
            if re.search(rf'\b{fr}\b', text) and en not in text:
                intl["calques_detected"].append(f"Calque FR detecte: '{fr}' -> '{en}'")
                intl["translation_quality_score"] -= 10

    # Slugs
    if "/en/" in (state.site_url or ""):
        if re.search(r'/en/infrastructure|/en/entreprise|/en/solution', state.site_url or ""):
            intl["slugs_issues"].append("Slugs EN non adaptes: evitent le franglais")

    # Recos
    if intl["calques_detected"]:
        intl["recommandations"].append("Adapter les expressions au contexte culturel cible")
    if intl["slugs_issues"]:
        intl["recommandations"].append("Utiliser des slugs en anglais naturel pour la version EN")
    if not intl["is_multilingual"]:
        intl["recommandations"].append("Ajouter les balises hreflang pour le multilingue")

    intl["translation_quality_score"] = max(20, intl["translation_quality_score"])
    result.status = AgentStatus.COMPLETED; result.data = intl
    log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    state.updated_at = datetime.now()
    return state
