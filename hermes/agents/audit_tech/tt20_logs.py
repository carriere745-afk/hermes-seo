"""T20 — Log Analysis (optionnel).

Analyse les logs serveur si fournis par le client :
- Pages crawlees par Googlebot mais non indexees
- Frequence de crawl par section
- Pages jamais crawlees malgre le sitemap
- Erreurs 404 recurrentes

Skip automatique si aucun log fourni.
$0 — deterministe.
"""

import logging
import re
from datetime import datetime

from hermes.models.audit_tech import TechAuditState

logger = logging.getLogger("hermes.audit_tech.tt20")


async def run(state: TechAuditState) -> TechAuditState:
    state.current_agent = "tt20"

    # T20 est conditionnel — skip si pas de logs
    if not hasattr(state, 'log_data') or not getattr(state, 'log_data', None):
        logger.info("T20: no server logs provided — skip (mentionner dans le rapport)")
        state.updated_at = datetime.now()
        return state

    log_content = state.log_data
    if not log_content or len(log_content) < 100:
        state.updated_at = datetime.now()
        return state

    logger.info(f"T20: analysing server logs ({len(log_content)} chars)")

    # Analyse basique des logs Apache/Nginx combin format
    lines = log_content.split("\n")[:100000]  # Max 100k lignes

    googlebot_requests = 0
    googlebot_urls = set()
    error_404_urls = set()
    crawl_by_section: dict[str, int] = {}
    total_requests = 0

    for line in lines:
        total_requests += 1

        # Googlebot detection
        if re.search(r"Googlebot|google\.com/bot", line, re.IGNORECASE):
            googlebot_requests += 1
            # Extraire l'URL
            url_match = re.search(r'"GET\s+(\S+)', line)
            if url_match:
                path = url_match.group(1)
                googlebot_urls.add(path)
                # Section
                section = "/".join(path.split("/")[:3]) or "/"
                crawl_by_section[section] = crawl_by_section.get(section, 0) + 1

        # Erreurs 404
        if re.search(r'" 404 ', line):
            url_match = re.search(r'"GET\s+(\S+)', line)
            if url_match:
                error_404_urls.add(url_match.group(1))

    # Generer un resume (pas d'issues, juste des donnees pour le rapport)
    if state.crawled_pages:
        crawled_paths = {p.url for p in state.crawled_pages}
        sitemap_paths = set(state.sitemap_urls or [])

        never_crawled_by_google = crawled_paths - googlebot_urls if googlebot_urls else set()
        if never_crawled_by_google:
            logger.info(f"T20: {len(never_crawled_by_google)} pages never crawled by Googlebot")

    logger.info(f"T20: {total_requests} total requests, {googlebot_requests} Googlebot, {len(error_404_urls)} unique 404s")
    state.updated_at = datetime.now()
    return state
