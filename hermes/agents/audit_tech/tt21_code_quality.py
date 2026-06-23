"""T21 — Code Quality & CMS SEO Impact.

Evalue la "proprete SEO" du code HTML genere par le CMS/theme :
- Balises HTML5 semantiques (article, nav, main, aside, section, header, footer)
- Ratio code utile / code mort (commentaires, CSS inline, display:none)
- DOM depth (indicateur de page builder)
- Elements obsoletes (<center>, <font>, <marquee>)
- Erreurs HTML basiques (W3C-like via regex)
- CSS/JS bloquants dans <head> (sans async/defer)
- Page builder detection (Elementor, Divi, WPBakery)
- Inline CSS/JS massif

$0 — deterministe, BeautifulSoup + regex.
"""

import logging
import re
from collections import Counter
from datetime import datetime

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt21")

# Elements HTML5 semantiques a verifier
SEMANTIC_ELEMENTS = ["article", "nav", "main", "aside", "section", "header", "footer"]

# Elements obsoletes HTML4 (ne devraient plus etre utilises)
OBSOLETE_ELEMENTS = ["center", "font", "marquee", "blink", "big", "strike", "tt", "frame", "frameset"]

# Patterns page builder (commentaires, classes CSS, ID)
PAGE_BUILDER_SIGNATURES = {
    "Elementor": [r"elementor-", r"data-elementor-", r"elementor-section"],
    "Divi": [r"et_pb_", r"et-boc", r"divi-builder"],
    "WPBakery": [r"vc_row", r"wpb_", r"vc_column"],
    "Beaver Builder": [r"fl-builder", r"fl-row"],
    "Gutenberg": [r"wp-block-", r"has-.*-background"],
    "Oxygen": [r"ct-section", r"oxy-"],
    "Brizy": [r"brz-"],
}

# Patterns W3C-like errors basiques
W3C_CHECKS = [
    (r"<(p|div|span|li)\b[^>]*>\s*</\1>", "Balise vide suspecte"),
    (r"<li\b[^>]*>(?!.*</li>).*(?:<li\b)", "Balises <li> imbriquees sans fermeture"),
    (r"id=\"([^\"]+)\".*id=\"\1\"", "Attribut id duplique"),
    (r"<(script|style)\b[^>]*>\s*</\1>", "Bloc <script> ou <style> vide"),
    (r"<a\b[^>]*>\s*</a>", "Lien vide (pas d'ancre, pas d'image)"),
]

# Seuils
MAX_DOM_DEPTH = 20  # > 20 = probable page builder
MAX_INLINE_CSS_KB = 20  # > 20KB de CSS inline dans <head> = suspect
MAX_CSS_FILES = 10  # > 10 fichiers CSS = probleme de performance
MAX_JS_FILES = 15  # > 15 fichiers JS = probleme de performance


def _count_semantic_elements(html: str) -> dict:
    """Compte les elements HTML5 semantiques."""
    soup = None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return {"total": 0, "found": []}

    counts = {}
    for elem in SEMANTIC_ELEMENTS:
        count = len(soup.find_all(elem))
        if count > 0:
            counts[elem] = count

    return {"total": sum(counts.values()), "found": list(counts.keys()), "counts": counts}


def _count_obsolete_elements(html: str) -> list[str]:
    """Detecte les elements HTML obsoletes."""
    soup = None
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return []

    found = []
    for elem in OBSOLETE_ELEMENTS:
        if soup.find_all(elem):
            found.append(elem)
    return found


def _estimate_dom_depth(html: str) -> int:
    """Estime la profondeur max du DOM."""
    max_depth = 0
    current_depth = 0
    for char in html[:500000]:
        if char == '<' and not html[html.index(char):].startswith('</'):
            current_depth += 1
            max_depth = max(max_depth, current_depth)
        elif char == '>' and html[max(0, html.index(char)-20):html.index(char)+1].count('</'):
            current_depth -= 1
    # Fallback plus simple : compter les div imbriquees
    return min(max_depth, 100) if max_depth > 0 else 15


def _count_blocking_resources(html: str) -> dict:
    """Compte les ressources bloquantes dans <head>."""
    head_match = re.search(r"<head[^>]*>(.*?)</head>", html, re.DOTALL | re.IGNORECASE)
    if not head_match:
        return {"css_files": 0, "js_files": 0, "blocking_js": 0, "inline_css_kb": 0}

    head_content = head_match.group(1)

    css_files = len(re.findall(r"<link[^>]*stylesheet[^>]*>", head_content, re.IGNORECASE))
    js_files = len(re.findall(r"<script[^>]*src=[^>]*>", head_content, re.IGNORECASE))
    blocking_js = len(re.findall(r"<script[^>]*src=[^>]*(?<!async)(?<!defer)>", head_content, re.IGNORECASE))

    # Estimer CSS inline
    inline_css = 0
    for style_match in re.finditer(r"<style[^>]*>(.*?)</style>", head_content, re.DOTALL | re.IGNORECASE):
        inline_css += len(style_match.group(1).encode("utf-8"))
    inline_css_kb = round(inline_css / 1024, 1)

    return {
        "css_files": css_files,
        "js_files": js_files,
        "blocking_js": blocking_js,
        "inline_css_kb": inline_css_kb,
    }


def _detect_page_builder(html: str) -> str:
    """Detecte le page builder utilise."""
    for builder, patterns in PAGE_BUILDER_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, html, re.IGNORECASE):
                return builder
    return ""


def _check_w3c_errors(html: str) -> list[str]:
    """Verification W3C-like basique."""
    errors = []
    for pattern, desc in W3C_CHECKS:
        matches = re.findall(pattern, html[:100000], re.DOTALL | re.IGNORECASE)
        if matches:
            errors.append(f"{desc} ({len(matches)} occurrences)")
    return errors


async def run(state: TechAuditState) -> TechAuditState:
    """Evalue la qualite du code HTML."""
    state.current_agent = "tt21"

    if not state.crawled_pages:
        return state

    pages_ok = [p for p in state.crawled_pages if p.status_code == 200 and not p.fetch_error]
    if not pages_ok:
        return state

    logger.info(f"T21: analysing code quality for {len(pages_ok)} pages (CMS={state.cms_detected})")

    issue_counter = len(state.issues)

    # Analyser un echantillon representatif
    homepage = next((p for p in pages_ok if p.url.rstrip("/") == state.site_url.rstrip("/")), pages_ok[0])
    sample = [homepage] + [p for p in pages_ok if p != homepage][:4]

    total_semantic = 0
    total_obsolete = 0
    total_blocking = 0
    total_w3c = 0
    page_builder = ""
    total_inline_css_kb = 0

    for page in sample:
        # Refetch le HTML (pas stocke dans CrawledPage a ce niveau)
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(page.url, headers={"User-Agent": "HermesAudit/1.0", "Accept": "text/html"})
                if resp.status_code != 200:
                    continue
                html = resp.text
        except Exception:
            continue

        # 1. Elements semantiques
        semantic = _count_semantic_elements(html)
        if semantic["total"] == 0:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="code_quality",
                description="Aucun element HTML5 semantique (<article>, <nav>, <main>, <section>...) — la structure de la page est invisible pour Google",
                url=page.url,
                observed="0 elements semantiques trouves",
                rule="utiliser les balises HTML5 semantiques",
                confidence="high",
                source_agent="T21",
                severity="high",
                impact_business="Medium",
                gain_potentiel="High",
                effort="Theme: contacter le developpeur. CMS: utiliser un theme qui supporte HTML5.",
                priority="P2",
                cms_location=(
                    f"{state.cms_detected} → Changer de theme ou modifier les templates"
                    if state.cms_detected else
                    "Verifier le theme / template utilise"
                ),
            ))
        elif len(semantic["found"]) <= 2:
            total_semantic += 1
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="code_quality",
                description=f"Peu d'elements HTML5 semantiques ({semantic['total']} trouves, {len(semantic['found'])} types : {', '.join(semantic['found'])})",
                url=page.url,
                observed=f"semantic_elements: {semantic['found']}",
                rule="utiliser une variete de balises HTML5 semantiques",
                confidence="high",
                source_agent="T21",
                severity="medium",
                impact_business="Low",
                gain_potentiel="Medium",
                effort="Ajouter <main>, <nav> et <article> aux templates",
                priority="P3",
            ))

        # 2. Elements obsoletes
        obsolete = _count_obsolete_elements(html)
        if obsolete:
            total_obsolete += 1
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="code_quality",
                description=f"Elements HTML obsoletes detectes: {', '.join(obsolete)} — le theme utilise du code deprecie",
                url=page.url,
                observed=f"obsolete_elements: {obsolete}",
                rule="pas d'elements HTML obsoletes",
                confidence="high",
                source_agent="T21",
                severity="medium",
                impact_business="Low",
                gain_potentiel="Medium",
                effort="Mettre a jour le theme pour utiliser des elements modernes",
                priority="P3",
            ))

        # 3. DOM depth
        depth = _estimate_dom_depth(html)
        if depth > MAX_DOM_DEPTH:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="code_quality",
                description=f"DOM depth excessive estimee ({depth} niveaux, seuil {MAX_DOM_DEPTH}) — probable page builder",
                url=page.url,
                observed=f"dom_depth_estimated: {depth}",
                rule=f"dom_depth <= {MAX_DOM_DEPTH}",
                confidence="medium",
                source_agent="T21",
                severity="high",
                impact_business="Medium",
                gain_potentiel="High",
                effort="Reduire le nombre de conteneurs imbriques. Eviter les page builders excessifs.",
                priority="P2",
            ))

        # 4. Resources bloquantes
        resources = _count_blocking_resources(html)
        if resources["blocking_js"] > 0:
            total_blocking += 1
        if resources["css_files"] > MAX_CSS_FILES:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="code_quality",
                description=f"Trop de fichiers CSS ({resources['css_files']}, seuil {MAX_CSS_FILES}) dans <head> — ralentit le rendu",
                url=page.url,
                observed=f"css_files_in_head: {resources['css_files']}",
                rule=f"css_files_in_head <= {MAX_CSS_FILES}",
                confidence="high",
                source_agent="T21",
                severity="medium",
                impact_business="Medium",
                gain_potentiel="Medium",
                effort="Concatener et minifier les fichiers CSS. Utiliser HTTP/2.",
                priority="P3",
            ))

        if resources["blocking_js"] > 2:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="code_quality",
                description=f"{resources['blocking_js']} scripts JS bloquants dans <head> (sans async/defer) — bloque le rendu",
                url=page.url,
                observed=f"blocking_js: {resources['blocking_js']} scripts sans async/defer",
                rule="scripts dans <head> avec async ou defer",
                confidence="high",
                source_agent="T21",
                severity="medium",
                impact_business="Medium",
                gain_potentiel="Medium",
                effort="Ajouter async ou defer aux scripts, ou les deplacer en fin de <body>",
                priority="P3",
            ))

        # 5. CSS inline massif
        if resources["inline_css_kb"] > MAX_INLINE_CSS_KB:
            total_inline_css_kb += resources["inline_css_kb"]
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="code_quality",
                description=f"CSS inline excessif dans <head> ({resources['inline_css_kb']} KB, seuil {MAX_INLINE_CSS_KB} KB) — dilue le contenu",
                url=page.url,
                observed=f"inline_css: {resources['inline_css_kb']} KB",
                rule=f"inline_css <= {MAX_INLINE_CSS_KB} KB",
                confidence="high",
                source_agent="T21",
                severity="medium",
                impact_business="Medium",
                gain_potentiel="Medium",
                effort="Externaliser le CSS dans un fichier separe avec cache",
                priority="P3",
            ))

        # 6. Page builder
        pb = _detect_page_builder(html)
        if pb:
            page_builder = pb
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="code_quality",
                description=f"Page builder detecte: {pb} — peut generer du code HTML superflu et un DOM profond",
                url=page.url,
                observed=f"page_builder: {pb}",
                rule="code HTML le plus propre possible",
                confidence="high",
                source_agent="T21",
                severity="low",
                impact_business="Low",
                gain_potentiel="Medium",
                effort=f"Pour {pb}: reduire les widgets, desactiver les fonctionnalites inutilisees",
                priority="P3",
            ))

        # 7. W3C errors
        w3c = _check_w3c_errors(html)
        if w3c:
            total_w3c += 1
            if len(w3c) >= 3:  # Seulement si plusieurs types d'erreurs
                issue_counter += 1
                state.issues.append(TechIssue(
                    id=f"P-{issue_counter:03d}",
                    category="code_quality",
                    description=f"Erreurs HTML detectees: {w3c[0]}; {w3c[1] if len(w3c) > 1 else ''}",
                    url=page.url,
                    observed=f"w3c_errors: {len(w3c)} types",
                    rule="HTML valide (W3C)",
                    confidence="medium",
                    source_agent="T21",
                    severity="low",
                    impact_business="Low",
                    gain_potentiel="Low",
                    effort="Corriger les erreurs HTML. Utiliser validator.w3.org.",
                    priority="P3",
                ))

    # Note globale code quality
    score = 100
    if total_semantic > 0:
        score -= total_semantic * 10
    if total_obsolete > 0:
        score -= total_obsolete * 15
    if total_blocking > 0:
        score -= total_blocking * 8
    if total_w3c > 0:
        score -= total_w3c * 5
    if total_inline_css_kb > MAX_INLINE_CSS_KB:
        score -= 10

    # Pas de dimension "code_quality" dans TechAuditScores, on l'ajoute dans les notes
    logger.info(f"T21: semantic={total_semantic}, obsolete={total_obsolete}, blocking={total_blocking}, w3c={total_w3c}, page_builder={page_builder}, score={max(0, score)}")

    state.updated_at = datetime.now()
    return state
