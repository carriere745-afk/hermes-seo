"""AC00 — Superviseur Audit de Contenu.

Garde-fou du pipeline. Verifie chaque transition, bloque si incoherence.
Pattern reutilise depuis Agent 00 (Superviseur Editorial).
"""

import re
from datetime import datetime

from hermes.models.audit import AuditSessionState


def validate_url(url: str) -> bool:
    """Verifie qu'une URL est valide."""
    return bool(re.match(r"^https?://", url))


async def run(state: AuditSessionState) -> AuditSessionState:
    """Verifie l'integrite de la session d'audit avant la transition suivante."""
    agent_id = "ac00"
    state.current_agent = agent_id

    # Verifier les URLs
    valid_urls = [u for u in state.urls if validate_url(u)]
    if not valid_urls:
        state.status = "blocked"
        return state
    state.urls = valid_urls

    # Verifier le mode
    if state.mode not in ("fast", "standard", "premium", "debug"):
        state.mode = "standard"

    state.status = "running"
    state.updated_at = datetime.now()
    return state
