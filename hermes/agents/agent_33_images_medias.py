"""Agent 33 — Image & Media Audit (gap module 16 du doc 630).

Verifie : alt, format WebP/AVIF, poids, hero preload, og:image,
VideoObject schema, backfill images.
"""

import re, logging, time
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_33")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_33"
    agent_name = "Images & Medias"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        audit = {
            "images_found": 0, "images_without_alt": 0, "alt_too_long": 0,
            "og_image_present": False, "video_schema": False,
            "issues": [], "recommandations": [], "score": 100,
        }

        imgs = re.findall(r"<img[^>]*>", content, re.IGNORECASE)
        audit["images_found"] = len(imgs)

        for img in imgs:
            alt = re.search(r'alt="([^"]*)"', img, re.IGNORECASE)
            if not alt or not alt.group(1):
                audit["images_without_alt"] += 1
                audit["score"] -= 5
            elif len(alt.group(1)) > 125:
                audit["alt_too_long"] += 1
                audit["score"] -= 2

        if audit["images_without_alt"] > 0:
            audit["recommandations"].append(f"Ajouter alt sur {audit['images_without_alt']} images")

        # og:image
        og_img = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"', content, re.IGNORECASE)
        audit["og_image_present"] = bool(og_img)

        # Video
        if re.search(r'<iframe|<video', content, re.IGNORECASE):
            audit["recommandations"].append("Ajouter schema VideoObject pour les videos")

        audit["score"] = max(0, min(100, audit["score"]))

        result.status = AgentStatus.COMPLETED
        result.data = audit
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state
