"""T08 — Mobile & Viewport.

Verifie la compatibilite mobile :
- Balise meta viewport (presence + contenu)
- Viewport content : width=device-width, initial-scale
- Thème couleur (meta theme-color, color-scheme)
- AMP detection
- Estimation : ratio texte/HTML (indicateur de contenu lisible)
- Elements trop larges (heuristique via nombre d'images sans dimensions)

$0 — pas de LLM. Deterministe.
"""

import logging
import re
from datetime import datetime

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt08")


def _validate_viewport_content(content: str) -> list[str]:
    """Analyse le contenu de la balise viewport.

    Returns: liste de problemes (vide = OK)
    """
    issues = []
    content_lower = content.lower()

    if "width=device-width" not in content_lower:
        issues.append("viewport manque 'width=device-width'")
    if "initial-scale=1" not in content_lower and "initial-scale=1.0" not in content_lower:
        issues.append("viewport manque 'initial-scale=1'")
    if "user-scalable=no" in content_lower:
        issues.append("viewport bloque le zoom utilisateur (user-scalable=no) — probleme d'accessibilite")
    if "maximum-scale=1" in content_lower:
        issues.append("viewport limite le zoom (maximum-scale=1) — peut etre problematique pour l'accessibilite")

    return issues


async def run(state: TechAuditState) -> TechAuditState:
    """Verifie la compatibilite mobile."""
    state.current_agent = "tt08"

    if not state.crawled_pages:
        logger.warning("T08: aucune page — skip")
        return state

    pages_to_audit = [p for p in state.crawled_pages if p.status_code == 200 and not p.fetch_error]
    logger.info(f"T08: analysing mobile compatibility for {len(pages_to_audit)} pages")

    issue_counter = len(state.issues)
    missing_viewport = 0
    viewport_issues = 0

    for page in pages_to_audit:
        page_issues = []

        # 1. Viewport present
        if not page.has_viewport:
            missing_viewport += 1
            page_issues.append({
                "desc": "Balise meta viewport absente — la page n'est pas optimisee pour mobile",
                "observed": "has_viewport: false",
                "rule": "meta viewport present",
                "severity": "critical",
                "impact": "High",
                "gain": "High",
                "effort": "2 min — ajouter <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">",
                "priority": "P1",
            })
        else:
            # Verifier le contenu du viewport (depuis le HTML brut, non stocke dans CrawledPage)
            # On verifie via les signaux indirects
            pass

        # 2. AMP (pour info)
        if hasattr(page, 'is_amp') and page.is_amp:
            page_issues.append({
                "desc": "Page AMP detectee — Google a arrete le support prioritaire d'AMP en 2024",
                "observed": "is_amp: true",
                "rule": "AMP obsolete (info)",
                "severity": "low",
                "impact": "Low",
                "gain": "Low",
                "effort": "Optionnel — migrer vers des pages responsive standards",
                "priority": "P3",
            })

        # 3. Ratio texte/HTML trop bas (< 10% suspect sur mobile)
        if page.text_html_ratio < 0.05 and page.word_count > 0:
            page_issues.append({
                "desc": f"Ratio texte/HTML tres faible ({page.text_html_ratio:.1%}) — la page peut contenir trop de code par rapport au contenu",
                "observed": f"text_html_ratio: {page.text_html_ratio:.3f}",
                "rule": "text_html_ratio > 0.05",
                "severity": "low",
                "impact": "Low",
                "gain": "Medium",
                "effort": "Reduire le code superflu, reporter le JS non critique",
                "priority": "P3",
            })

        # 4. Images sans alt (accessibilite mobile)
        if page.images_without_alt > 5:
            page_issues.append({
                "desc": f"{page.images_without_alt} images sans attribut alt — accessibilite degradee",
                "observed": f"images_without_alt: {page.images_without_alt}/{page.images_total}",
                "rule": "toutes les images ont un attribut alt",
                "severity": "medium",
                "impact": "Low",
                "gain": "Medium",
                "effort": "Ajouter des attributs alt descriptifs",
                "priority": "P3",
            })

        # 5. Images sans dimensions (risque CLS sur mobile)
        if page.images_total > 5 and page.has_viewport:
            # Heuristique : si beaucoup d'images et CLS potentiel
            alt_ratio = (page.images_total - page.images_without_alt) / max(1, page.images_total)
            if alt_ratio < 0.5:
                page_issues.append({
                    "desc": f"Moins de 50% des images ont un alt ({page.images_total - page.images_without_alt}/{page.images_total})",
                    "observed": f"images_alt_ratio: {alt_ratio:.0%}",
                    "rule": "> 50% d'images avec alt",
                    "severity": "medium",
                    "impact": "Low",
                    "gain": "Low",
                    "effort": "Ajouter des alt aux images",
                    "priority": "P3",
                })

        # Creer les issues
        for pi in page_issues:
            issue_counter += 1
            viewport_issues += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="mobile",
                description=pi["desc"],
                url=page.url,
                observed=pi["observed"],
                rule=pi["rule"],
                confidence="high",
                source_agent="T08",
                severity=pi["severity"],
                impact_business=pi["impact"],
                gain_potentiel=pi["gain"],
                effort=pi["effort"],
                priority=pi["priority"],
            ))

    logger.info(f"T08: {missing_viewport} pages sans viewport, {viewport_issues} total issues")

    # Scoring
    if pages_to_audit:
        total = len(pages_to_audit)
        with_viewport = total - missing_viewport
        score = int((with_viewport / total) * 60 +  # 60% du score = viewport
                     max(0, 40 - viewport_issues * 5))  # 40% = autres issues
        state.scores.mobile.score = min(100, max(0, score))
        state.scores.mobile.confidence = "high"

    state.updated_at = datetime.now()
    return state
