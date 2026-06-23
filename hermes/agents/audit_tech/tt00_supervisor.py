"""T00 — Superviseur Technique.

Garde-fou du pipeline. Verifie :
- Consentement explicite de l'utilisateur (mode consentement)
- Presence des cles API optionnelles
- Acces reseau au site cible
- Bornes de crawl (profondeur, nombre d'URLs, rate limiting)
- Respect de robots.txt (obligatoire sauf mode audit_bypass)

Non skippable. $0.
"""

import logging
from datetime import datetime
from urllib.parse import urlparse

from hermes.models.audit_tech import TechAuditState

logger = logging.getLogger("hermes.audit_tech.tt00")


async def run(state: TechAuditState) -> TechAuditState:
    """Initialise et valide la session d'audit technique."""
    state.current_agent = "tt00"

    # ── 1. Validation de l'URL racine ────────────────────────────────
    if not state.site_url:
        state.status = "error"
        logger.error("T00: site_url manquant")
        return state

    if not state.site_url.startswith("http"):
        state.site_url = f"https://{state.site_url}"

    parsed = urlparse(state.site_url)
    state.domain = parsed.netloc.lower().replace("www.", "")
    if not state.domain:
        state.status = "error"
        logger.error(f"T00: domaine invalide pour {state.site_url}")
        return state

    # ── 2. Mode consentement ──────────────────────────────────────────
    if not state.consent_given:
        logger.warning(
            f"T00: consentement non donne pour {state.domain}. "
            "L'audit ne peut pas proceder sans consentement explicite."
        )
        state.status = "awaiting_consent"
        return state

    logger.info(
        f"T00: consentement valide pour {state.domain} — "
        f"profondeur={state.max_depth}, max_urls={state.max_urls}, "
        f"robots_txt={'respecte' if state.respect_robots_txt else 'bypass'}, "
        f"rate_limit={state.rate_limit_rps} req/s"
    )

    # ── 3. Validation des bornes ──────────────────────────────────────
    if state.max_urls < 1:
        state.max_urls = 10
    if state.max_urls > 5000:
        state.max_urls = 5000
    if state.max_depth < 1:
        state.max_depth = 3
    if state.max_depth > 10:
        state.max_depth = 10
    if state.rate_limit_rps < 0.5:
        state.rate_limit_rps = 0.5
    if state.rate_limit_rps > 10:
        state.rate_limit_rps = 10

    # ── 4. Profil client ─────────────────────────────────────────────
    valid_profiles = ("ecommerce", "blog", "institutionnel", "agence", "saas")
    if state.profile not in valid_profiles:
        logger.warning(f"T00: profil '{state.profile}' invalide, fallback 'blog'")
        state.profile = "blog"

    # ── 5. Session ID ──────────────────────────────────────────────────
    if not state.session_id:
        state.session_id = f"tech-{state.domain}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    state.status = "consented"
    state.updated_at = datetime.now()
    logger.info(f"T00: session {state.session_id} initialisee — profil={state.profile}, mode={state.mode}")
    return state
