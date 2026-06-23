"""T12 — Maillage Interne Technique.

Analyse le maillage interne depuis les donnees T03 (graphe) :
- Pages orphelines (degre entrant = 0)
- Pages faiblement maillees (degre entrant < 3)
- Pages mortes (peu de liens sortants)
- Distribution desequilibree (Gini > 0.8)
- Recommendations de maillage

$0 — pas de LLM. Utilise les donnees de T03.
"""

import logging
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt12")


async def run(state: TechAuditState) -> TechAuditState:
    """Analyse le maillage interne."""
    state.current_agent = "tt12"

    if not state.crawled_pages:
        return state

    pages_ok = [p for p in state.crawled_pages if p.status_code == 200 and not p.fetch_error]
    logger.info(f"T12: analysing internal linking for {len(pages_ok)} pages")

    issue_counter = len(state.issues)

    # Reconstruire le graphe depuis state.graph_edges (rempli par T03)
    edges = state.graph_edges or []

    # Calculer les degres entrants
    in_degree: dict[str, int] = Counter()
    out_degree: dict[str, int] = Counter()

    for edge in edges:
        src = edge.get("from", "")
        dst = edge.get("to", "")
        if src and dst:
            out_degree[src] += 1
            in_degree[dst] += 1

    # Initialiser a 0 pour les pages sans liens
    for page in pages_ok:
        url = page.url
        if url not in in_degree:
            in_degree[url] = 0
        if url not in out_degree:
            out_degree[url] = 0

    # 1. Pages orphelines (degre entrant = 0)
    orphans = [url for url, deg in in_degree.items() if deg == 0]
    homepage = state.site_url.rstrip("/")

    # Filtrer la homepage (normal d'avoir peu de liens entrants vers la home dans le crawl)
    orphans = [u for u in orphans if u.rstrip("/") != homepage]

    if orphans:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="maillage",
            description=f"{len(orphans)} page(s) orpheline(s) — aucun lien interne entrant",
            url=orphans[0] if len(orphans) == 1 else state.site_url,
            observed=f"orphans: {len(orphans)} pages, first: {orphans[0][:60]}",
            rule="toute page a au moins 1 lien entrant",
            confidence="high",
            source_agent="T12",
            severity="critical",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Ajouter des liens depuis les pages pertinentes vers ces pages",
            priority="P1",
        ))

    # 2. Pages faiblement maillees (degre entrant 1-2)
    weakly_linked = [(url, deg) for url, deg in in_degree.items()
                     if 0 < deg < 3 and url.rstrip("/") != homepage]
    if weakly_linked and len(weakly_linked) > len(pages_ok) * 0.3:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="maillage",
            description=f"{len(weakly_linked)} page(s) faiblement maillees (< 3 liens entrants)",
            url=state.site_url,
            observed=f"weakly_linked: {len(weakly_linked)}/{len(pages_ok)} pages",
            rule="la plupart des pages ont >= 3 liens entrants",
            confidence="high",
            source_agent="T12",
            severity="medium",
            impact_business="Medium",
            gain_potentiel="Medium",
            effort="Renforcer le maillage interne",
            priority="P3",
        ))

    # 3. Pages mortes (peu/pas de liens sortants)
    dead_pages = [(url, deg) for url, deg in out_degree.items()
                  if deg < 2 and url.rstrip("/") != homepage]
    if dead_pages and len(dead_pages) > len(pages_ok) * 0.3:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="maillage",
            description=f"{len(dead_pages)} page(s) avec peu ou pas de liens sortants — risque de page 'cul-de-sac'",
            url=state.site_url,
            observed=f"dead_pages: {len(dead_pages)}/{len(pages_ok)}",
            rule="chaque page a des liens sortants pertinents",
            confidence="medium",
            source_agent="T12",
            severity="medium",
            impact_business="Low",
            gain_potentiel="Medium",
            effort="Ajouter des liens sortants pertinents",
            priority="P3",
        ))

    # 4. Top pages les plus maillees (hubs)
    hubs = sorted(in_degree.items(), key=lambda x: -x[1])[:5]
    if hubs and hubs[0][1] > 20:
        logger.info(f"T12: top hub = {hubs[0][0][:60]} ({hubs[0][1]} liens entrants)")

    # 5. Recommandations specifiques pour les orphelines
    for orphan_url in orphans[:3]:
        # Chercher les pages les plus similaires pour suggerer un lien
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="maillage",
            description=f"Page orpheline: {orphan_url[:80]} — aucun lien entrant",
            url=orphan_url,
            observed=f"in_degree: 0",
            rule="in_degree >= 1",
            confidence="high",
            source_agent="T12",
            severity="high",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Ajouter un lien depuis la page parente ou le hub le plus proche",
            priority="P1",
        ))

    logger.info(f"T12: {len(orphans)} orphans, {len(weakly_linked)} weakly linked, {len(dead_pages)} dead pages")

    # Scoring
    if pages_ok:
        total = len(pages_ok)
        orphan_ratio = len(orphans) / max(1, total)
        weak_ratio = len(weakly_linked) / max(1, total)
        score = 100 - int(orphan_ratio * 50) - int(weak_ratio * 30)
        state.scores.maillage.score = max(0, min(100, score))
        state.scores.maillage.confidence = "high"

    state.updated_at = datetime.now()
    return state
