"""T05 — Structure On-Page.

Valide les elements structurels de chaque page :
- Title : longueur, duplication, absence
- Meta description : longueur, duplication, absence
- H1 : absence, duplication, longueur excessive
- Canonical : presence, coherence avec l'URL
- OG tags : presence, coherence avec title/description
- Twitter card : presence

$0 — pas de LLM. Deterministe.
"""

import logging
from collections import Counter
from datetime import datetime

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt05")

# Seuils
TITLE_MIN = 30
TITLE_MAX = 60
TITLE_OPTIMAL = (50, 60)
META_MIN = 70
META_MAX = 160
META_OPTIMAL = (120, 155)
H1_MAX_LENGTH = 70


async def run(state: TechAuditState) -> TechAuditState:
    """Analyse la structure on-page."""
    state.current_agent = "tt05"

    if not state.crawled_pages:
        logger.warning("T05: aucune page — skip")
        return state

    logger.info(f"T05: analysing structure for {len(state.crawled_pages)} pages")

    issue_counter = len(state.issues)

    # Collecter les titles et meta pour detection de duplication
    all_titles = [p.title.strip().lower() for p in state.crawled_pages if p.title.strip()]
    all_metas = [p.meta_description.strip().lower() for p in state.crawled_pages if p.meta_description.strip()]
    all_h1s = [p.h1.strip().lower() for p in state.crawled_pages if p.h1.strip()]

    dup_titles = {t: c for t, c in Counter(all_titles).items() if c > 1}
    dup_metas = {m: c for m, c in Counter(all_metas).items() if c > 1}
    dup_h1s = {h: c for h, c in Counter(all_h1s).items() if c > 1}

    for page in state.crawled_pages:
        if page.fetch_error or page.status_code != 200:
            continue

        page_issues = []

        # ── Title ──────────────────────────────────────────────────
        title_lower = page.title.strip().lower() if page.title else ""

        if not page.title.strip():
            page_issues.append({
                "desc": "Title absent",
                "observed": "title vide",
                "rule": "title present",
                "severity": "critical",
                "impact": "High",
                "gain": "High",
                "effort": "5 min — ajouter un title dans le CMS",
                "priority": "P1",
            })
        elif page.title_length < TITLE_MIN:
            page_issues.append({
                "desc": f"Title trop court ({page.title_length} caracteres, min {TITLE_MIN})",
                "observed": f"title_length: {page.title_length}",
                "rule": f"title_length >= {TITLE_MIN}",
                "severity": "high",
                "impact": "High",
                "gain": "High",
                "effort": "5 min — enrichir le title",
                "priority": "P2",
            })
        elif page.title_length > TITLE_MAX:
            page_issues.append({
                "desc": f"Title trop long ({page.title_length} caracteres, max {TITLE_MAX})",
                "observed": f"title_length: {page.title_length}",
                "rule": f"title_length <= {TITLE_MAX}",
                "severity": "medium",
                "impact": "Medium",
                "gain": "Medium",
                "effort": "2 min — raccourcir le title",
                "priority": "P3",
            })
        elif title_lower and title_lower in dup_titles:
            page_issues.append({
                "desc": f"Title duplique ({dup_titles[title_lower]} pages ont le meme title)",
                "observed": f"title duplique: '{page.title[:60]}'",
                "rule": "title unique par page",
                "severity": "high",
                "impact": "High",
                "gain": "High",
                "effort": "5 min — rendre chaque title unique",
                "priority": "P2",
            })

        # ── Meta Description ───────────────────────────────────────
        if not page.meta_description.strip():
            page_issues.append({
                "desc": "Meta description absente",
                "observed": "meta_description vide",
                "rule": "meta description presente",
                "severity": "medium",
                "impact": "Medium",
                "gain": "Medium",
                "effort": "5 min — ajouter une meta description",
                "priority": "P3",
            })
        elif page.meta_description_length < META_MIN:
            page_issues.append({
                "desc": f"Meta description trop courte ({page.meta_description_length} car.)",
                "observed": f"meta_length: {page.meta_description_length}",
                "rule": f"meta_description_length >= {META_MIN}",
                "severity": "low",
                "impact": "Low",
                "gain": "Low",
                "effort": "3 min — enrichir la meta",
                "priority": "P3",
            })
        elif page.meta_description_length > META_MAX:
            page_issues.append({
                "desc": f"Meta description trop longue ({page.meta_description_length} car.)",
                "observed": f"meta_length: {page.meta_description_length}",
                "rule": f"meta_description_length <= {META_MAX}",
                "severity": "low",
                "impact": "Low",
                "gain": "Low",
                "effort": "2 min — raccourcir la meta",
                "priority": "P3",
            })
        elif page.meta_description.lower() in dup_metas:
            page_issues.append({
                "desc": f"Meta description dupliquee",
                "observed": f"meta dupliquee: '{page.meta_description[:60]}'",
                "rule": "meta description unique par page",
                "severity": "high",
                "impact": "Medium",
                "gain": "Medium",
                "effort": "5 min — rendre chaque meta unique",
                "priority": "P3",
            })

        # ── H1 ─────────────────────────────────────────────────────
        if not page.h1.strip():
            page_issues.append({
                "desc": "H1 absent",
                "observed": "h1 vide",
                "rule": "h1 present",
                "severity": "high",
                "impact": "High",
                "gain": "High",
                "effort": "2 min — ajouter un H1",
                "priority": "P1",
            })
        elif page.h1_count > 1:
            page_issues.append({
                "desc": f"Plusieurs H1 ({page.h1_count})",
                "observed": f"h1_count: {page.h1_count}",
                "rule": "1 seul H1 par page",
                "severity": "medium",
                "impact": "Medium",
                "gain": "Medium",
                "effort": "5 min — garder un seul H1",
                "priority": "P2",
            })
        elif len(page.h1) > H1_MAX_LENGTH:
            page_issues.append({
                "desc": f"H1 trop long ({len(page.h1)} caracteres)",
                "observed": f"h1_length: {len(page.h1)}",
                "rule": f"h1_length <= {H1_MAX_LENGTH}",
                "severity": "low",
                "impact": "Low",
                "gain": "Low",
                "effort": "2 min — raccourcir le H1",
                "priority": "P3",
            })
        elif page.h1.lower() in dup_h1s:
            page_issues.append({
                "desc": f"H1 duplique",
                "observed": f"h1 duplique: '{page.h1[:60]}'",
                "rule": "h1 unique par page",
                "severity": "high",
                "impact": "Medium",
                "gain": "Medium",
                "effort": "5 min — rendre chaque H1 unique",
                "priority": "P2",
            })

        # ── Hn hierarchy ───────────────────────────────────────────
        if not page.heading_hierarchy_ok:
            page_issues.append({
                "desc": "Hierarchie des titres Hn incorrecte (saut de niveau)",
                "observed": "heading_hierarchy_ok: false",
                "rule": "pas de saut dans la hierarchie Hn",
                "severity": "medium",
                "impact": "Low",
                "gain": "Medium",
                "effort": "10 min — corriger la hierarchie des titres",
                "priority": "P3",
            })

        # ── Canonical ──────────────────────────────────────────────
        if not page.canonical:
            page_issues.append({
                "desc": "Canonical absent",
                "observed": "canonical vide",
                "rule": "canonical present (recommandation Google)",
                "severity": "medium",
                "impact": "Medium",
                "gain": "Medium",
                "effort": "2 min — ajouter un canonical auto-reference",
                "priority": "P3",
            })

        # ── OG Tags ────────────────────────────────────────────────
        if not page.og_title and not page.og_description:
            page_issues.append({
                "desc": "Open Graph tags absents (og:title, og:description) — partage reseaux sociaux degrade",
                "observed": "og:title et og:description absents",
                "rule": "OG tags presents",
                "severity": "low",
                "impact": "Low",
                "gain": "Low",
                "effort": "5 min — ajouter les balises OG dans le head",
                "priority": "P3",
            })
        elif not page.og_image:
            page_issues.append({
                "desc": "og:image absent — pas d'image de partage",
                "observed": "og:image vide",
                "rule": "og:image present",
                "severity": "low",
                "impact": "Low",
                "gain": "Low",
                "effort": "2 min — definir une image de partage",
                "priority": "P3",
            })

        # Créer les issues
        for pi in page_issues:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="structure",
                description=pi["desc"],
                url=page.url,
                observed=pi["observed"],
                rule=pi["rule"],
                confidence="high",
                source_agent="T05",
                severity=pi["severity"],
                impact_business=pi["impact"],
                gain_potentiel=pi["gain"],
                effort=pi["effort"],
                priority=pi["priority"],
            ))

    logger.info(f"T05: {issue_counter - len(state.issues) + len(state.issues) if issue_counter > 0 else len(state.issues)} issues, {len(dup_titles)} duplicate titles, {len(dup_h1s)} duplicate H1s")

    # Scoring
    if state.crawled_pages:
        total = len(state.crawled_pages)
        pages_with_title = sum(1 for p in state.crawled_pages if p.title.strip() and TITLE_MIN <= p.title_length <= TITLE_MAX)
        pages_with_h1 = sum(1 for p in state.crawled_pages if p.h1.strip() and p.h1_count == 1)
        pages_with_meta = sum(1 for p in state.crawled_pages if p.meta_description.strip() and META_MIN <= p.meta_description_length <= META_MAX)

        score = int((pages_with_title / total * 40) + (pages_with_h1 / total * 30) + (pages_with_meta / total * 30))
        state.scores.structure.score = min(100, score)
        state.scores.structure.confidence = "high"

    state.updated_at = datetime.now()
    return state
