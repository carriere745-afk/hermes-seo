"""T02 — Indexation (GSC ou Fallback).

Verifie le statut d'indexation de chaque page :
- Mode GSC connecte : URL Inspection API (statut exact, confidence high)
- Mode GSC non connecte : analyse des signaux (noindex, robots.txt, canonical)
  -> indexabilite technique probable (confidence medium)
  Aucun test site:URL — trop peu fiable.

Sortie : pour chaque URL, statut + confidence + recommandation.
$0 — pas de LLM.
"""

import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt02")

# Statuts d'indexation possibles
INDEX_STATUS = {
    "indexed": {"label": "Indexee", "confidence": "high", "severity": "info"},
    "not_indexed_noindex": {"label": "Non indexee (noindex volontaire)", "confidence": "high", "severity": "info"},
    "not_indexed_blocked": {"label": "Non indexee (bloquee robots.txt)", "confidence": "high", "severity": "high"},
    "not_indexed_error": {"label": "Non indexee (erreur crawl)", "confidence": "high", "severity": "critical"},
    "probably_indexable": {"label": "Indexabilite technique probable", "confidence": "medium", "severity": "info"},
    "probably_not_indexable": {"label": "Probablement non indexable", "confidence": "medium", "severity": "medium"},
    "unknown": {"label": "Indexation reelle non confirmee", "confidence": "low", "severity": "info"},
}


def _estimate_indexability(page) -> tuple[str, list[str]]:
    """Estime l'indexabilite sans GSC.

    Analyse : robots meta noindex, robots.txt blockage, canonical, status code.

    Returns: (status_key, [notes])
    """
    notes = []

    if page.status_code != 200:
        return "probably_not_indexable", [f"HTTP {page.status_code} — non crawlable"]

    if page.has_noindex:
        notes.append("Balise meta robots: noindex")
        return "not_indexed_noindex", notes

    if page.robots_blocked:
        notes.append("Bloquee par robots.txt")
        return "not_indexed_blocked", notes

    # Verifier canonical coherence
    if page.canonical and page.canonical != page.url:
        notes.append(f"Canonical different: {page.canonical[:80]}")

    # Page avec contenu > 0 et pas de blocage = probablement indexable
    if page.word_count > 0:
        return "probably_indexable", notes

    return "unknown", ["Impossible de determiner l'indexabilite — connectez GSC"]


async def _check_gsc_indexation(state: TechAuditState, page) -> Optional[tuple[str, list[str]]]:
    """Verifie l'indexation via GSC si connecte.

    Returns: (status_key, notes) ou None si GSC non dispo.
    """
    try:
        from hermes.connectors.gsc_connector import gsc

        if not gsc.is_configured:
            return None

        domain = urlparse(state.site_url).netloc.replace("www.", "")
        site_url_gsc = f"sc-domain:{domain}"

        result = await gsc.check_indexation(site_url_gsc, page.url)
        if result is None:
            return None

        coverage = result.get("coverage_state", "")
        notes = [
            f"GSC: {coverage}",
            f"Last crawled: {result.get('last_crawled', 'inconnu')}",
        ]
        robots = result.get("robots_txt", "")
        if robots and "BLOCKED" in robots.upper():
            notes.append("GSC confirme: bloquee par robots.txt")

        if coverage in ("Indexed", "indexed", "Submitted and indexed"):
            return "indexed", notes
        elif "noindex" in coverage.lower():
            return "not_indexed_noindex", notes
        elif "error" in coverage.lower() or "crawl" in coverage.lower():
            return "not_indexed_error", notes
        else:
            return "probably_not_indexable", notes

    except Exception as e:
        logger.debug(f"T02: GSC check failed for {page.url}: {e}")
        return None


async def run(state: TechAuditState) -> TechAuditState:
    """Verifie le statut d'indexation de chaque page."""
    state.current_agent = "tt02"

    if not state.crawled_pages:
        logger.warning("T02: aucune page — skip")
        return state

    # Tester GSC une fois
    gsc_available = False
    try:
        from hermes.connectors.gsc_connector import gsc
        gsc_available = gsc.is_configured
    except Exception:
        pass

    logger.info(f"T02: checking indexation for {len(state.crawled_pages)} pages (GSC={'connected' if gsc_available else 'unavailable'})")

    stats = {
        "indexed": 0, "not_indexed_noindex": 0, "not_indexed_blocked": 0,
        "not_indexed_error": 0, "probably_indexable": 0,
        "probably_not_indexable": 0, "unknown": 0,
    }

    issue_counter = len(state.issues)

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        status_key = "unknown"
        notes = []

        # 1. Essayer GSC
        if gsc_available:
            gsc_result = await _check_gsc_indexation(state, page)
            if gsc_result:
                status_key, notes = gsc_result

        # 2. Fallback heuristique
        if status_key == "unknown" or not gsc_available:
            status_key, notes = _estimate_indexability(page)

        stats[status_key] = stats.get(status_key, 0) + 1

        # Generer une issue si probleme
        info = INDEX_STATUS.get(status_key, INDEX_STATUS["unknown"])
        if info["severity"] in ("critical", "high", "medium"):
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="indexation",
                description=f"Page {info['label']} : {page.url[:80]}",
                url=page.url,
                observed="; ".join(notes) if notes else info["label"],
                rule="indexation verifiee",
                confidence=info["confidence"],
                source_agent="T02",
                severity=info["severity"],
                impact_business="High" if info["severity"] in ("critical", "high") else "Medium",
                gain_potentiel="High" if info["severity"] == "critical" else "Medium",
                effort="Verifier et corriger l'indexabilite",
                priority="P1" if info["severity"] == "critical" else "P2",
            ))

    logger.info(
        f"T02: indexation check done — "
        f"indexed={stats['indexed']}, noindex={stats['not_indexed_noindex']}, "
        f"blocked={stats['not_indexed_blocked']}, errors={stats['not_indexed_error']}, "
        f"probably_ok={stats['probably_indexable']}, unknown={stats['unknown']}"
    )

    # Si GSC non connecte, ajouter une note informative
    if not gsc_available:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="indexation",
            description="GSC non connecte — les statuts d'indexation sont estimes, pas confirmes. Connectez GSC pour des donnees exactes.",
            url=state.site_url,
            observed="GSC unavailable",
            rule="GSC recommande pour audit complet",
            confidence="low",
            source_agent="T02",
            severity="low",
            impact_business="Low",
            gain_potentiel="Medium",
            effort="Connecter GSC OAuth",
            priority="P3",
        ))

    # Mettre a jour les scores
    total = max(1, len(state.crawled_pages))
    indexable = stats["indexed"] + stats["probably_indexable"]
    state.scores.indexation.score = min(100, int((indexable / total) * 100))
    state.scores.indexation.confidence = "high" if gsc_available else "medium"

    state.updated_at = datetime.now()
    return state
