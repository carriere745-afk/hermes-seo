"""T07 — Performance (Core Web Vitals).

Mesure les performances selon les Core Web Vitals :
- Source 1 : PageSpeed Insights API (CrUX terrain + Lighthouse lab)
  -> confidence "high" (CrUX) / "medium" (lab)
- Source 2 : Estimation heuristique (taille page, TTFB, load time)
  -> confidence "low"

Distinction claire terrain / lab / heuristique dans le rapport.
$0 — PageSpeed Insights API gratuite, pas de LLM.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt07")

# Nombre max de pages a analyser via PSI (eviter depassement quota)
MAX_PSI_PAGES = 20

# Seuils CWV
LCP_GOOD = 2500   # ms
LCP_POOR = 4000
CLS_GOOD = 0.1
CLS_POOR = 0.25
INP_GOOD = 200    # ms
INP_POOR = 500


async def run(state: TechAuditState) -> TechAuditState:
    """Analyse les performances CWV de chaque page."""
    state.current_agent = "tt07"

    if not state.crawled_pages:
        logger.warning("T07: aucune page — skip")
        return state

    # Determiner quelles pages analyser via PSI
    pages_to_audit = [p for p in state.crawled_pages if p.status_code == 200 and not p.fetch_error]

    # Prioriser la homepage + pages importantes
    homepage = next((p for p in pages_to_audit if p.url.rstrip("/") == state.site_url.rstrip("/")), None)
    psi_pages = pages_to_audit[:MAX_PSI_PAGES]
    if homepage and homepage not in psi_pages:
        psi_pages = [homepage] + psi_pages[:MAX_PSI_PAGES - 1]

    # 0. Essayer GSC Core Web Vitals (donnees terrain, confidence high)
    gsc_cwv = None
    try:
        from hermes.connectors.gsc_connector import gsc
        if gsc.is_configured:
            domain = state.domain
            site_url_gsc = f"sc-domain:{domain}"
            # GSC CWV via query (dimension device)
            cwv_data = await gsc.query(
                site_url_gsc,
                start_date=(datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                dimensions=["page"],
                row_limit=100,
            )
            if cwv_data:
                gsc_cwv = cwv_data
                logger.info(f"T07: GSC CWV data available ({len(gsc_cwv)} pages)")
    except Exception as e:
        logger.debug(f"T07: GSC CWV unavailable ({e})")

    logger.info(f"T07: analysing performance for {len(pages_to_audit)} pages (PSI: {len(psi_pages)}, heuristic: rest)")

    issue_counter = len(state.issues)
    psi_available = True

    # Tester PSI sur la homepage d'abord
    try:
        from hermes.connectors.pagespeed_connector import analyze_page

        test_psi = await analyze_page(psi_pages[0].url, strategy="mobile")
        if test_psi.get("error"):
            logger.warning(f"T07: PSI unavailable, falling back to heuristic — {test_psi['error']}")
            psi_available = False
    except Exception as e:
        logger.warning(f"T07: PSI import failed — {e}")
        psi_available = False

    # Analyser chaque page
    scores = []

    for page in pages_to_audit:
        cwv_data = None

        # PSI pour les premieres pages
        if psi_available and page in psi_pages:
            try:
                cwv_data = await analyze_page(page.url, strategy="mobile")
            except Exception as e:
                logger.debug(f"T07: PSI failed for {page.url}: {e}")

        # Fallback heuristique
        if cwv_data is None or cwv_data.get("error"):
            from hermes.connectors.pagespeed_connector import estimate_cwv_heuristic
            cwv_data = estimate_cwv_heuristic(
                page_size_kb=page.page_size_kb,
                ttfb_ms=page.ttfb_ms,
                load_time_ms=page.load_time_ms,
                images_count=page.images_total,
                external_resources=page.external_links_count,
            )

        scores.append(cwv_data.get("performance_score", 0))

        # Issues LCP
        lcp = cwv_data.get("lcp", {})
        if lcp.get("label") == "poor":
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="performance",
                description=f"LCP deficient ({lcp['value']}ms, seuil {LCP_GOOD}ms) — le contenu principal met trop de temps a s'afficher",
                url=page.url,
                observed=f"LCP: {lcp['value']}ms, source: {cwv_data.get('source', 'heuristic')}",
                rule=f"LCP < {LCP_GOOD}ms (good)",
                confidence=cwv_data.get("confidence", "low"),
                source_agent="T07",
                severity="high" if lcp["value"] > LCP_POOR else "medium",
                impact_business="High",
                gain_potentiel="High",
                effort="Optimiser les images, le serveur, le CSS critique. Voir PageSpeed Insights pour details.",
                priority="P2",
            ))
        elif lcp.get("label") == "needs improvement":
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="performance",
                description=f"LCP a ameliorer ({lcp['value']}ms, visez < {LCP_GOOD}ms)",
                url=page.url,
                observed=f"LCP: {lcp['value']}ms",
                rule=f"LCP < {LCP_GOOD}ms",
                confidence=cwv_data.get("confidence", "low"),
                source_agent="T07",
                severity="medium",
                impact_business="Medium",
                gain_potentiel="Medium",
                effort="Reduire le temps de reponse serveur et optimiser les images",
                priority="P3",
            ))

        # Issues CLS
        cls = cwv_data.get("cls", {})
        if cls.get("label") == "poor":
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="performance",
                description=f"CLS excessif ({cls['value']}, seuil {CLS_GOOD}) — la mise en page est instable",
                url=page.url,
                observed=f"CLS: {cls['value']}, source: {cwv_data.get('source', 'heuristic')}",
                rule=f"CLS < {CLS_GOOD} (good)",
                confidence=cwv_data.get("confidence", "low"),
                source_agent="T07",
                severity="high",
                impact_business="High",
                gain_potentiel="High",
                effort="Reserver l'espace pour les images, polices et contenu dynamique",
                priority="P2",
            ))
        elif cls.get("label") == "needs improvement":
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="performance",
                description=f"CLS a ameliorer ({cls['value']}, visez < {CLS_GOOD})",
                url=page.url,
                observed=f"CLS: {cls['value']}",
                rule=f"CLS < {CLS_GOOD}",
                confidence=cwv_data.get("confidence", "low"),
                source_agent="T07",
                severity="medium",
                impact_business="Medium",
                gain_potentiel="Medium",
                effort="Stabiliser la mise en page",
                priority="P3",
            ))

        # Pages lourdes (> 500 KB)
        if page.page_size_kb > 500:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="performance",
                description=f"Page trop lourde ({page.page_size_kb:.0f} KB, visez < 500 KB)",
                url=page.url,
                observed=f"page_size: {page.page_size_kb:.0f} KB",
                rule="page_size < 500 KB",
                confidence="high",
                source_agent="T07",
                severity="medium",
                impact_business="Medium",
                gain_potentiel="Medium",
                effort="Compresser les images, minifier CSS/JS, activer la compression GZip",
                priority="P3",
            ))

    # Scoring
    if pages_to_audit:
        good_lcp = sum(1 for s in scores if s >= 90)
        needs_work = sum(1 for s in scores if 50 <= s < 90)
        poor = sum(1 for s in scores if s < 50)

        total = len(pages_to_audit)
        score = int((good_lcp * 100 + needs_work * 60 + poor * 20) / max(1, total))
        state.scores.performance.score = score
        state.scores.performance.confidence = "high" if psi_available else "low"

    logger.info(f"T07: avg_score={state.scores.performance.score}, PSI={'available' if psi_available else 'unavailable'}")
    state.updated_at = datetime.now()
    return state
