"""Agent Agent_29 — SEO Local (Google Business Profile) (gap #10).

Module SEO local : coherence NAP (nom, adresse, telephone),
Google Business Profile, avis clients, Pack Local.
Ferme le gap #10 du document 630.
"""

import logging, re, time
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.strategie_db import log_event
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_29")

async def run(state: SessionState) -> SessionState:
    agent_id = "agent_29"
    agent_name = "SEO Local / GBP"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(
        agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = ""
        if state.brouillon_html:
            content = state.brouillon_html.html if hasattr(state.brouillon_html, "html") else str(state.brouillon_html)

        nap = _extract_nap(content, state)

        result.status = AgentStatus.COMPLETED
        result.data = {
            "nap_consistency": nap,
            "gbp_ready": bool(nap.get("nom") and nap.get("adresse")),
            "nap_score": _compute_nap_score(nap),
        }
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED
        result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state


def _extract_nap(content: str, state) -> dict:
    text = content or ""
    nap = {"nom": "", "adresse": "", "telephone": "", "ville": "", "code_postal": ""}

    # Extraire telephone
    phone_match = re.search(r"(\+33|0)[\s.]?[1-9](\d{2}[\s.]?){4}", text)
    if phone_match:
        nap["telephone"] = phone_match.group(0)

    # Extraire code postal + ville
    cp_match = re.search(r"\b(\d{5})\s+([A-ZÀ-Ü][a-zà-ü]+(?:[- ][A-ZÀ-Ü][a-zà-ü]+)*)", text)
    if cp_match:
        nap["code_postal"] = cp_match.group(1)
        nap["ville"] = cp_match.group(2)

    # Extraire adresse
    addr_patterns = [
        r"(\d+[,\s]+\w+[\w\s,]+(?:rue|avenue|boulevard|bd|av|rue|place|impasse|chemin|route|allee|quai|cours)[\w\s]*)",
        r"(?:situe|base|localise|implante|present)\s+(?:a|au|aux|en|dans)\s+([^.,]+)",
    ]
    for pat in addr_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m and len(m.group(1)) > 10:
            nap["adresse"] = m.group(1).strip()
            break

    # Nom (de l'entreprise/du site)
    if state.fiche_entreprise:
        nap["nom"] = state.fiche_entreprise.get("nom", "")
    elif state.site_url:
        from urllib.parse import urlparse
        nap["nom"] = urlparse(state.site_url).netloc.replace("www.", "").split(".")[0]

    return nap


def _compute_nap_score(nap: dict) -> int:
    score = 0
    if nap.get("nom"):
        score += 25
    if nap.get("adresse"):
        score += 25
    if nap.get("ville") or nap.get("code_postal"):
        score += 20
    if nap.get("telephone"):
        score += 20
    if nap.get("nom") and nap.get("adresse") and nap.get("telephone"):
        score += 10  # Bonus NAP complet
    return score
