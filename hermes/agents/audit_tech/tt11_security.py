"""T11 — Securite & Headers (defensif).

Verifie la configuration de securite de maniere defensive :
- HTTPS avec certificat valide
- Redirection HTTP → HTTPS
- Headers de securite : HSTS, CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy, Permissions-Policy
- Mixed content detection (ressources HTTP sur page HTTPS)

Defensif : HEAD/GET publiques uniquement, pas de scanning, pas de test d'intrusion.
$0 — utilise security_headers.py (wrapper shcheck).
"""

import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt11")

UA = "HermesAudit/1.0"

HEADER_SEVERITY = {
    "Strict-Transport-Security": "high",
    "Content-Security-Policy": "medium",
    "X-Frame-Options": "medium",
    "X-Content-Type-Options": "low",
    "Referrer-Policy": "low",
    "Permissions-Policy": "low",
}


async def _detect_mixed_content(page_url: str, html_snippet: str) -> list[str]:
    """Detecte les ressources HTTP sur une page HTTPS (mixed content)."""
    issues = []
    if not page_url.startswith("https"):
        return issues

    import re
    # Chercher les URLs HTTP dans src, href, url()
    http_patterns = re.findall(r"""(?:src|href|url)\s*=\s*["']http://[^"']+""", html_snippet[:50000], re.IGNORECASE)
    if http_patterns:
        for match in http_patterns[:5]:
            url_match = re.search(r"http://[^\s\"']+", match)
            if url_match:
                issues.append(f"Ressource en HTTP: {url_match.group()[:80]}")

    return issues


async def run(state: TechAuditState) -> TechAuditState:
    """Analyse la securite du site."""
    state.current_agent = "tt11"

    if not state.crawled_pages:
        return state

    pages_ok = [p for p in state.crawled_pages if p.status_code == 200 and not p.fetch_error]
    logger.info(f"T11: checking security for {len(pages_ok)} pages")

    issue_counter = len(state.issues)
    securite_issues = 0

    # 1. HTTPS global + redirect HTTP→HTTPS (via connecteur)
    from hermes.connectors.security_headers import check_https_only
    https_result = await check_https_only(state.site_url)

    if not https_result["https_works"]:
        securite_issues += 1
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="security",
            description="HTTPS non fonctionnel — le site n'est pas servi en HTTPS",
            url=state.site_url,
            observed="HTTPS connection failed",
            rule="site accessible en HTTPS",
            confidence="high",
            source_agent="T11",
            severity="critical",
            impact_business="High",
            gain_potentiel="High",
            effort="Installer un certificat SSL/TLS sur le serveur",
            priority="P0",
        ))

    if https_result["https_works"] and not https_result["https_redirect"]:
        securite_issues += 1
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="security",
            description="HTTP ne redirige pas vers HTTPS",
            url=f"http://{urlparse(state.site_url).netloc}",
            observed="HTTP 200 sans redirection HTTPS",
            rule="HTTP → HTTPS (301 redirect)",
            confidence="high",
            source_agent="T11",
            severity="high",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Configurer une redirection 301 HTTP → HTTPS",
            priority="P1",
        ))

    # 2. Headers de securite (via connecteur shcheck)
    from hermes.connectors.security_headers import check_security_headers
    sec_result = await check_security_headers(state.site_url)

    score_security = sec_result.get("score", 100)
    raw_headers = sec_result.get("raw_headers", {})

    for issue in sec_result.get("issues", []):
        if not issue["found"]:
            hdr = issue["header"]
            sev = HEADER_SEVERITY.get(hdr, "low")
            securite_issues += 1
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="security",
                description=f"Header de securite manquant: {hdr}",
                url=state.site_url,
                observed=f"{hdr}: absent",
                rule=f"{hdr} present",
                confidence="high",
                source_agent="T11",
                severity=sev,
                impact_business="Low",
                gain_potentiel="Medium",
                effort=issue.get("recommendation", f"Ajouter le header {hdr}"),
                priority="P3" if sev == "low" else "P2",
                cms_location=(
                    "Ajouter dans .htaccess (Apache) ou nginx.conf"
                    if state.cms_detected in ("WordPress", "PrestaShop")
                    else "Configurer le header dans le serveur web"
                ),
            ))

    # 3. Mixed content (par page, echantillonnage)
    mixed_content_pages = 0
    for page in pages_ok[:5]:  # Verifier les 5 premieres pages
        if page.url.startswith("https"):
            # On refetch juste le head pour ne pas surcharger
            try:
                import httpx as _httpx
                async with _httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    resp = await client.get(page.url, headers={"User-Agent": UA, "Accept": "text/html"})
                    if resp.status_code == 200:
                        mixed = await _detect_mixed_content(page.url, resp.text[:50000])
                        for mix in mixed:
                            mixed_content_pages += 1
                            issue_counter += 1
                            state.issues.append(TechIssue(
                                id=f"P-{issue_counter:03d}",
                                category="security",
                                description=f"Mixed content detecte: {mix}",
                                url=page.url,
                                observed=mix,
                                rule="pas de ressources HTTP sur page HTTPS",
                                confidence="high",
                                source_agent="T11",
                                severity="high",
                                impact_business="Medium",
                                gain_potentiel="Medium",
                                effort="Remplacer les URLs HTTP par HTTPS",
                                priority="P2",
                            ))
            except Exception:
                pass

    logger.info(f"T11: {securite_issues} security issues, {mixed_content_pages} mixed content pages")

    # Scoring
    state.scores.security.score = max(0, min(100, score_security))
    state.scores.security.confidence = "high"

    state.updated_at = datetime.now()
    return state
