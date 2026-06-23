"""T10 — International & Hreflang.

Verifie la configuration multilingue :
- Presence de hreflang (via donnees T01)
- Validation structurelle (return tags, x-default, codes langue)
- Coherence : hreflang pointe vers des pages 200 OK
- Verification des codes ISO 639-1 valides

Reutilise hermes/connectors/hreflang_validator.py (wrapper polly).
$0 — pas de LLM.
"""

import logging
import re
from datetime import datetime
from urllib.parse import urlparse

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt10")


def _check_lang_code(lang: str) -> bool:
    """Verifie si un code langue est ISO 639-1 valide."""
    if lang.lower() == "x-default":
        return True
    return bool(re.match(r"^[a-z]{2}(-[A-Z]{2})?$", lang))


def _extract_lang_from_html(page) -> str:
    """Determine la langue de la page (html[lang], hreflang self-ref)."""
    # Chercher un hreflang x-default ou self-referencing
    for tag in page.hreflang_tags:
        href = tag.get("href", "")
        if href.rstrip("/") == page.url.rstrip("/") and tag.get("hreflang"):
            return tag["hreflang"]
    return page.language_detected or ""


async def run(state: TechAuditState) -> TechAuditState:
    """Verifie la configuration hreflang / internationale."""
    state.current_agent = "tt10"

    if not state.crawled_pages:
        return state

    pages_ok = [p for p in state.crawled_pages if p.status_code == 200 and not p.fetch_error]
    logger.info(f"T10: checking international/hreflang for {len(pages_ok)} pages")

    issue_counter = len(state.issues)

    # Determiner si le site est multilingue
    has_hreflang = any(p.hreflang_tags for p in pages_ok)
    langs_detected = set()
    for p in pages_ok:
        for tag in p.hreflang_tags:
            hl = tag.get("hreflang", "")
            if hl:
                langs_detected.add(hl)
        if p.language_detected:
            langs_detected.add(p.language_detected)

    is_multilingual = len(langs_detected) > 1

    if not has_hreflang and len(langs_detected) <= 1:
        # Site monolingue, pas de hreflang necessaire
        logger.info("T10: site monolingue — hreflang non requis")
        state.scores.international.score = 100
        state.scores.international.confidence = "high"
        state.updated_at = datetime.now()
        return state

    # 1. Validation des balises hreflang (reutilise le connecteur polly)
    hreflang_errors = 0
    pages_with_hreflang = 0

    for page in pages_ok:
        if not page.hreflang_tags:
            continue

        pages_with_hreflang += 1
        from hermes.connectors.hreflang_validator import validate_hreflang_tags
        result = validate_hreflang_tags(page.hreflang_tags, page.url)

        for err in result.get("errors", []):
            hreflang_errors += 1
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="international",
                description=f"Hreflang: {err}",
                url=page.url,
                observed=err,
                rule="hreflang valide",
                confidence="high",
                source_agent="T10",
                severity="high" if "retour" in err.lower() or "x-default" in err.lower() else "medium",
                impact_business="High" if "x-default" in err.lower() else "Medium",
                gain_potentiel="High" if "x-default" in err.lower() else "Medium",
                effort="Corriger les balises hreflang",
                priority="P2",
            ))

        # Verifier les codes langue invalides
        for tag in page.hreflang_tags:
            hl = tag.get("hreflang", "")
            if hl and not _check_lang_code(hl):
                issue_counter += 1
                state.issues.append(TechIssue(
                    id=f"P-{issue_counter:03d}",
                    category="international",
                    description=f"Code hreflang invalide: '{hl}' (doit etre ISO 639-1: fr, en, de...)",
                    url=page.url,
                    observed=f"hreflang: {hl}",
                    rule="code langue ISO 639-1",
                    confidence="high",
                    source_agent="T10",
                    severity="high",
                    impact_business="High",
                    gain_potentiel="Medium",
                    effort="5 min — corriger le code langue",
                    priority="P2",
                ))

    # 2. Coherence langue HTML vs hreflang
    for page in pages_ok[:20]:
        html_lang = page.language_detected
        hreflang_langs = [t["hreflang"] for t in page.hreflang_tags if not t.get("is_x_default")]

        if html_lang and hreflang_langs and html_lang not in hreflang_langs:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="international",
                description=f"Incoherence: html[lang]='{html_lang}' mais hreflang={hreflang_langs}",
                url=page.url,
                observed=f"html_lang={html_lang}, hreflang={hreflang_langs}",
                rule="html[lang] coherent avec hreflang",
                confidence="high",
                source_agent="T10",
                severity="medium",
                impact_business="Medium",
                gain_potentiel="Medium",
                effort="Aligner html[lang] avec le hreflang de la page",
                priority="P3",
            ))

    # 3. S'il y a du hreflang mais pas sur toutes les pages
    if has_hreflang and pages_with_hreflang < len(pages_ok) * 0.8:
        missing = len(pages_ok) - pages_with_hreflang
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="international",
            description=f"{missing} page(s) sans balises hreflang alors que le site est multilingue",
            url=state.site_url,
            observed=f"pages_without_hreflang: {missing}/{len(pages_ok)}",
            rule="toutes les pages ont des balises hreflang",
            confidence="high",
            source_agent="T10",
            severity="high",
            impact_business="High",
            gain_potentiel="High",
            effort="Ajouter les balises hreflang sur toutes les pages",
            priority="P2",
        ))

    logger.info(f"T10: {pages_with_hreflang} pages hreflang, {hreflang_errors} erreurs, {len(langs_detected)} langues")

    # Scoring
    total = max(1, len(pages_ok))
    score = 100
    if has_hreflang:
        score -= min(40, hreflang_errors * 10)
        coverage = pages_with_hreflang / total
        score = int(score * coverage)
    state.scores.international.score = max(0, min(100, score))
    state.scores.international.confidence = "high"

    state.updated_at = datetime.now()
    return state
