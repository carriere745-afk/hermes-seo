"""T13 — Anomalies Critiques.

Detecte les anomalies critiques qui impactent directement le SEO :
- Pages en erreur 5xx
- Boucles de redirection (chaine > 3)
- Canonicals contradictoires (page A pointe vers B, B pointe vers C)
- Pages avec noindex + dans le sitemap
- URLs avec status 404 dans le sitemap
- Temps de chargement extremes (> 5 secondes)

$0 — pas de LLM.
"""

import logging
from collections import defaultdict
from datetime import datetime

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt13")


async def run(state: TechAuditState) -> TechAuditState:
    state.current_agent = "tt13"
    if not state.crawled_pages:
        return state

    issue_counter = len(state.issues)
    pages_ok = [p for p in state.crawled_pages if not p.fetch_error]

    # 1. Pages en erreur 5xx
    errors_5xx = [p for p in state.crawled_pages if 500 <= p.status_code < 600]
    if errors_5xx:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}", category="anomalies",
            description=f"{len(errors_5xx)} page(s) en erreur serveur (5xx)",
            url=errors_5xx[0].url, observed=f"status: {errors_5xx[0].status_code}",
            rule="pas d'erreur 5xx", confidence="high", source_agent="T13",
            severity="critical", impact_business="High", gain_potentiel="High",
            effort="Verifier les logs serveur, corriger les erreurs applicatives",
            priority="P0",
        ))

    # 2. Boucles de redirection
    for page in pages_ok:
        if page.redirect_count > 3:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}", category="anomalies",
                description=f"Chaine de redirections longue ({page.redirect_count} redirections)",
                url=page.url, observed=f"redirect_count: {page.redirect_count}",
                rule="redirect_count <= 3", confidence="high", source_agent="T13",
                severity="high", impact_business="Medium", gain_potentiel="High",
                effort="Reduire la chaine de redirection a 1-2 sauts max",
                priority="P1",
            ))

    # 3. Pages 404
    errors_404 = [p for p in state.crawled_pages if p.status_code == 404]
    if errors_404:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}", category="anomalies",
            description=f"{len(errors_404)} page(s) en erreur 404",
            url=errors_404[0].url, observed=f"status: 404",
            rule="pas de 404 dans les pages importantes", confidence="high",
            source_agent="T13", severity="high", impact_business="Medium",
            gain_potentiel="High", effort="Corriger les liens ou creer des redirections 301",
            priority="P1",
        ))

    # 4. Canonicals contradictoires (A → B, B → C)
    canonicals = {}
    for page in pages_ok:
        if page.canonical and page.canonical != page.url:
            canonicals[page.url] = page.canonical

    for src, target in canonicals.items():
        if target in canonicals:  # B pointe ailleurs → contradiction
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}", category="anomalies",
                description=f"Canonical contradictoire: {src} → {target} → {canonicals[target]}",
                url=src, observed=f"canonical chain: {src} -> {target} -> {canonicals[target]}",
                rule="pas de chaine de canonicals", confidence="high", source_agent="T13",
                severity="high", impact_business="High", gain_potentiel="High",
                effort="Corriger les canonicals pour qu'ils pointent directement vers l'URL canonique finale",
                priority="P1",
            ))

    # 5. Pages noindex + dans le sitemap
    sitemap_urls = set(state.sitemap_urls or [])
    for page in pages_ok:
        if page.has_noindex and page.url in sitemap_urls:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}", category="anomalies",
                description="Page en noindex presente dans le sitemap — signaux contradictoires",
                url=page.url, observed="has_noindex: true, in_sitemap: true",
                rule="pas de noindex + sitemap", confidence="high", source_agent="T13",
                severity="high", impact_business="High", gain_potentiel="High",
                effort="Retirer la page du sitemap OU enlever le noindex",
                priority="P1",
            ))

    # 6. Temps de chargement extremes
    slow_pages = [p for p in pages_ok if p.load_time_ms > 5000]
    if slow_pages:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}", category="anomalies",
            description=f"{len(slow_pages)} page(s) extremement lentes (> 5s)",
            url=slow_pages[0].url, observed=f"load_time: {slow_pages[0].load_time_ms}ms",
            rule="load_time < 5000ms", confidence="high", source_agent="T13",
            severity="high", impact_business="High", gain_potentiel="High",
            effort="Optimiser le temps de reponse serveur, les images, le code",
            priority="P1",
        ))

    # Collecter les critical issues
    state.critical_issues = [i for i in state.issues if i.severity == "critical"]

    logger.info(f"T13: {len(errors_5xx)} 5xx, {len(errors_404)} 404, {len(slow_pages)} slow pages, {len(state.critical_issues)} critical")
    state.updated_at = datetime.now()
    return state
