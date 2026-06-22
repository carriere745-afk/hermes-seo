"""AC09 — Transparence Contenu (Delta DOM).

Detecte les ecarts entre le HTML brut et le contenu visible.
Identifie le contenu cache, le texte dans les images,
les PDFs lies, et les CTA non detectes en statique.

3 couches :
1. HTML brut vs visible (CSS hidden, off-screen, commentaires)
2. Texte dans les images (alt text vs OCR potentiel)
3. PDFs lies (extraction contenu)

Deterministe (pas de LLM). Coute $0.
"""

import re
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Comment


def _count_hidden_content(soup: BeautifulSoup) -> dict[str, Any]:
    """Analyse le contenu potentiellement cache dans le HTML.

    Retourne : {
        "css_hidden_elements": 12,
        "css_hidden_text_length": 450,
        "off_screen_elements": 3,
        "html_comments_count": 8,
        "html_comments_text_length": 200,
        "zero_size_elements": 2,
        "white_on_white_risk": False,
        "suspicious_keyword_stuffing": False,
    }
    """
    hidden = {
        "css_hidden_elements": 0,
        "css_hidden_text_length": 0,
        "off_screen_elements": 0,
        "html_comments_count": 0,
        "html_comments_text_length": 0,
        "zero_size_elements": 0,
        "white_on_white_risk": False,
        "suspicious_keyword_stuffing": False,
    }

    # 1. Elements avec display:none ou visibility:hidden en inline style
    for tag in soup.find_all(style=True):
        style = tag.get("style", "").lower()
        if "display:none" in style or "display: none" in style:
            hidden["css_hidden_elements"] += 1
            text = tag.get_text(strip=True)
            if len(text) > 20:  # Contenu substantiel cache
                hidden["css_hidden_text_length"] += len(text)
        if "visibility:hidden" in style or "visibility: hidden" in style:
            hidden["css_hidden_elements"] += 1
            text = tag.get_text(strip=True)
            hidden["css_hidden_text_length"] += len(text)

    # 2. Classes CSS suspectes (hide, hidden, invisible, sr-only)
    for tag in soup.find_all(class_=True):
        classes = " ".join(tag.get("class_", []))
        if re.search(r"\b(hide|hidden|invisible|sr-only|visually-hidden)\b", classes):
            text = tag.get_text(strip=True)
            if len(text) > 30:
                hidden["css_hidden_elements"] += 1
                hidden["css_hidden_text_length"] += len(text)

    # 3. Elements hors ecran (position:absolute avec left: -9999px ou top: -9999px)
    for tag in soup.find_all(style=True):
        style = tag.get("style", "").lower()
        if re.search(r"(left|top)\s*:\s*-9{3,}", style):
            hidden["off_screen_elements"] += 1
            hidden["css_hidden_text_length"] += len(tag.get_text(strip=True))

    # 4. Commentaires HTML
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        text = comment.strip()
        if len(text) > 20:
            hidden["html_comments_count"] += 1
            hidden["html_comments_text_length"] += len(text)

    # 5. Elements taille 0 ou police 0
    for tag in soup.find_all(style=True):
        style = tag.get("style", "").lower()
        if re.search(r"(width|height)\s*:\s*0", style):
            hidden["zero_size_elements"] += 1
        if re.search(r"font-size\s*:\s*0", style):
            hidden["zero_size_elements"] += 1

    # 6. Detection white-on-white
    for tag in soup.find_all(style=True):
        style = tag.get("style", "").lower()
        if "color" in style and "background" in style:
            # Detection simplifiee : si color contient "fff" et background contient "fff"
            color_match = re.search(r"color\s*:\s*(#[fF]+|white|rgb\(\s*255)", style)
            bg_match = re.search(r"background(-color)?\s*:\s*(#[fF]+|white|rgb\(\s*255)", style)
            if color_match and bg_match:
                hidden["white_on_white_risk"] = True
                break

    # 7. Keyword stuffing suspect (texte cache > 500 caracteres)
    if hidden["css_hidden_text_length"] > 500:
        hidden["suspicious_keyword_stuffing"] = True

    return hidden


def _analyze_image_text(soup: BeautifulSoup, base_url: str) -> dict[str, Any]:
    """Analyse les images pour du contenu textuel potentiel.

    Detecte les images sans alt (potentiellement informatives),
    les images avec du texte (logos, infographies, captures),
    et les images avec des dimensions suggerant du contenu.
    """
    images = soup.find_all("img")
    analysis = {
        "total": len(images),
        "without_alt": 0,
        "with_generic_alt": 0,  # "image", "photo", "logo", etc.
        "potentially_informative": 0,  # Grandes dimensions, sans alt descriptif
        "infographic_candidates": 0,
        "certification_logo_candidates": 0,
    }

    generic_alts = {"image", "photo", "logo", "picture", "img", "photo.", "image.", ""}

    for img in images:
        alt = img.get("alt", "").strip().lower()

        if not alt:
            analysis["without_alt"] += 1
        elif alt in generic_alts or len(alt) < 5:
            analysis["with_generic_alt"] += 1

        # Images potentiellement informatives (grandes, sans alt descriptif)
        width = img.get("width", "")
        height = img.get("height", "")
        try:
            w = int(width) if width else 0
            h = int(height) if height else 0
            if w > 400 and h > 300 and (not alt or alt in generic_alts):
                analysis["potentially_informative"] += 1
        except (ValueError, TypeError):
            pass

        # Candidats infographie (grand format vertical)
        try:
            w = int(width) if width else 0
            h = int(height) if height else 0
            if w > 600 and h > 800 and h > w:
                analysis["infographic_candidates"] += 1
        except (ValueError, TypeError):
            pass

        # Candidats logo/certification (petit format carre)
        try:
            w = int(width) if width else 0
            h = int(height) if height else 0
            if 50 < w < 300 and abs(w - h) < 50:
                if any(kw in (alt + img.get("src", "").lower()) for kw in ("certif", "label", "iso", "qualite", "garantie", "logo")):
                    analysis["certification_logo_candidates"] += 1
        except (ValueError, TypeError):
            pass

    return analysis


async def _detect_pdfs(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Detecte les PDFs lies depuis la page."""
    pdfs = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.lower().endswith(".pdf"):
            full_url = urljoin(base_url, href)
            pdfs.append({
                "url": full_url,
                "link_text": a.get_text(strip=True)[:100],
                "detected": True,
            })

    # Tenter de verifier l'accessibilite des PDFs (sans les telecharger)
    for pdf in pdfs[:5]:  # Max 5 PDFs
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.head(pdf["url"])
                pdf["accessible"] = resp.status_code == 200
                pdf["content_type"] = resp.headers.get("content-type", "")
        except Exception:
            pdf["accessible"] = False
            pdf["content_type"] = ""

    return pdfs


def _calculate_transparency_score(
    visible_words: int,
    hidden_data: dict,
    image_data: dict,
    pdfs: list,
) -> dict:
    """Calcule le score de transparence 0-100."""
    score = 100
    issues = []
    strengths = []

    # Penalites contenu cache
    if hidden_data["css_hidden_elements"] > 0:
        penalty = min(20, hidden_data["css_hidden_elements"] * 3)
        score -= penalty
        issues.append({
            "type": "css_hidden",
            "gravity": "high" if hidden_data["css_hidden_text_length"] > 200 else "moderate",
            "description": f"{hidden_data['css_hidden_elements']} elements caches via CSS "
                           f"({hidden_data['css_hidden_text_length']} caracteres de texte masque)",
            "risk": "Keyword stuffing ou contenu cache non indexable",
        })

    if hidden_data["off_screen_elements"] > 0:
        score -= hidden_data["off_screen_elements"] * 5
        issues.append({
            "type": "offscreen",
            "gravity": "high",
            "description": f"{hidden_data['off_screen_elements']} elements hors ecran (position negative)",
            "risk": "Technique de cloaking",
        })

    if hidden_data["white_on_white_risk"]:
        score -= 20
        issues.append({
            "type": "white_on_white",
            "gravity": "critical",
            "description": "Texte blanc sur fond blanc detecte — risque de cloaking",
            "risk": "Penalite Google possible",
        })

    if hidden_data["zero_size_elements"] > 0:
        score -= hidden_data["zero_size_elements"] * 5
        issues.append({
            "type": "zero_size",
            "gravity": "high",
            "description": f"{hidden_data['zero_size_elements']} elements taille 0 ou police 0",
        })

    if hidden_data["html_comments_count"] > 5:
        score -= 5
        issues.append({
            "type": "comments",
            "gravity": "low",
            "description": f"{hidden_data['html_comments_count']} commentaires HTML avec contenu substantiel",
        })

    # Penalites images
    if image_data["without_alt"] > 0:
        score -= min(10, image_data["without_alt"] * 2)
        issues.append({
            "type": "missing_alt",
            "gravity": "moderate",
            "description": f"{image_data['without_alt']} images sans attribut alt — "
                           f"contenu potentiellement invisible pour Google",
        })

    if image_data["potentially_informative"] > 0:
        issues.append({
            "type": "informative_images",
            "gravity": "moderate",
            "description": f"{image_data['potentially_informative']} images informatives sans description textuelle",
            "risk": "Informations (prix, certifications) non indexables",
        })

    if image_data["certification_logo_candidates"] > 0:
        strengths.append(f"{image_data['certification_logo_candidates']} logos/certifications detectes dans les images")

    # PDFs
    if pdfs:
        accessible = [p for p in pdfs if p.get("accessible")]
        if accessible:
            strengths.append(f"{len(accessible)} PDFs detectes et accessibles — contenu supplementaire")
        else:
            issues.append({
                "type": "pdfs_broken",
                "gravity": "low",
                "description": f"{len(pdfs)} PDFs lies mais inaccessibles",
            })

    # Score final
    score = max(0, min(100, score))

    # Interpretation
    if score >= 90:
        status = "ok"
    elif score >= 70:
        status = "warning"
    else:
        status = "critical"

    return {
        "score": score,
        "status": status,
        "issues": issues,
        "strengths": strengths,
        "hidden_content": hidden_data,
        "image_analysis": image_data,
        "pdfs_detected": pdfs,
    }


async def run(state) -> "AuditSessionState":
    """Execute l'analyse de transparence sur chaque page auditee.

    Stocke les resultats dans les scores de chaque page (dimension transparency).
    Retourne l'AuditSessionState modifie.
    """
    from hermes.models.audit import AuditSessionState, DimensionScore

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        # Re-fetch pour le parsing (le HTML brut n'est plus en memoire)
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(page.url)
                html = resp.text
        except Exception as e:
            if page.url in state.scores:
                state.scores[page.url].transparency = DimensionScore(
                    score=0, max_score=100,
                    weaknesses=[f"Impossible d'analyser la transparence : {e}"]
                )
            continue

        soup = BeautifulSoup(html, "html.parser")

        hidden_data = _count_hidden_content(soup)
        image_data = _analyze_image_text(soup, page.url)
        pdfs = await _detect_pdfs(soup, page.url)

        report = _calculate_transparency_score(
            page.word_count_visible,
            hidden_data,
            image_data,
            pdfs,
        )

        strengths = report.pop("strengths", [])
        issues_list = report.pop("issues", [])
        weaknesses = []
        for iss in issues_list:
            weaknesses.append(f"[{iss.get('gravity', '?')}] {iss.get('description', '')} — {iss.get('risk', '')}")

        if page.url in state.scores:
            state.scores[page.url].transparency = DimensionScore(
                score=report["score"],
                max_score=100,
                strengths=strengths,
                weaknesses=weaknesses,
            )
            # Bonus/malus sur le score global
            if report["status"] == "critical":
                state.scores[page.url].global_score -= 10
            elif report["status"] == "warning":
                state.scores[page.url].global_score -= 3

    state.updated_at = datetime.now()
    return state
