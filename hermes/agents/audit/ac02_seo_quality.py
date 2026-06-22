"""AC02 — Scoring SEO On-Page + Qualite Editoriale.

Evalue les fondamentaux SEO et la qualite du contenu.
Deterministe (pas de LLM). Reutilise scoring_rules.py + content_guard.py.
"""

import re
from datetime import datetime

from hermes.models.audit import AuditSessionState, AuditScores, DimensionScore, CrawledPage


def _score_title(page: CrawledPage) -> int:
    """Score title (0-20)."""
    score = 0
    if page.title:
        score += 5  # Present
        if 50 <= page.title_length <= 65:
            score += 5  # Longueur optimale
        elif 40 <= page.title_length <= 75:
            score += 3
        if page.h1 and _overlap(page.title, page.h1) > 30:
            score += 3  # Cohérence avec H1
    return min(20, score)


def _score_meta(page: CrawledPage) -> int:
    """Score meta description (0-15)."""
    score = 0
    if page.meta_description:
        score += 3
        if 140 <= page.meta_description_length <= 160:
            score += 4
        elif 100 <= page.meta_description_length <= 200:
            score += 2
        cta_words = ("decouvrez", "consultez", "comparez", "guide", "gratuit", "complet")
        if any(w in page.meta_description.lower() for w in cta_words):
            score += 2
    return min(15, score)


def _score_h1(page: CrawledPage) -> int:
    """Score H1 (0-15)."""
    score = 0
    if page.h1 and page.h1_count == 1:
        score += 8  # Present et unique
    elif page.h1:
        score += 5  # Present mais multiple
    if page.h1 and page.title and _overlap(page.h1, page.title) > 20:
        score += 3
    return min(15, score)


def _score_hn(page: CrawledPage) -> int:
    """Score Hn (0-15)."""
    score = 0
    if page.heading_hierarchy_ok:
        score += 5
    h2_count = len(page.h2_list)
    if h2_count >= 5:
        score += 5
    elif h2_count >= 3:
        score += 3
    elif h2_count >= 1:
        score += 1

    # Diversite des H2 (pas de doublons)
    unique_h2 = len(set(h.lower() for h in page.h2_list))
    if h2_count > 0 and unique_h2 == h2_count:
        score += 3

    # Ratio H2 en questions (bon pour AEO)
    question_h2 = sum(1 for h in page.h2_list if "?" in h or h.startswith(("comment", "pourquoi", "quoi", "quand", "quel", "qui", "ou")))
    if h2_count > 0 and question_h2 / h2_count >= 0.3:
        score += 2

    return min(15, score)


def _score_images(page: CrawledPage) -> int:
    """Score images (0-10)."""
    score = 0
    if page.images_total > 0:
        alt_pct = page.images_with_alt / page.images_total
        if alt_pct >= 0.8:
            score += 5
        elif alt_pct >= 0.5:
            score += 3
    if page.images_lazy > 0:
        score += 2
    if page.images_with_dimensions > page.images_total * 0.5:
        score += 1
    return min(10, score)


def _score_links(page: CrawledPage) -> int:
    """Score liens (0-10)."""
    score = 0
    if page.internal_links >= 3:
        score += 4
    elif page.internal_links >= 1:
        score += 2
    # Ancres descriptives
    bad_anchors = ("cliquez ici", "en savoir plus", "lire la suite", "click here")
    good_count = sum(
        1 for l in page.internal_links_list
        if l.get("ancre", "") and not any(b in l["ancre"].lower() for b in bad_anchors)
    )
    if page.internal_links > 0 and good_count / max(1, page.internal_links) > 0.7:
        score += 3
    if page.broken_links == 0:
        score += 1
    return min(10, score)


def _score_density(page: CrawledPage) -> int:
    """Score densite mots-cles (0-10). A defaut de mot-cle connu, base sur la densite de contenu."""
    score = 5  # Neutre
    if page.word_count > 0 and page.text_html_ratio > 10:
        score += 3
    if page.word_count >= 600:
        score += 2
    return min(10, score)


def _score_coherence(page: CrawledPage) -> int:
    """Score coherence globale (0-5)."""
    score = 0
    # H1 / title / meta coherents
    if page.title and page.h1 and _overlap(page.title, page.h1) > 15:
        score += 2
    if page.title and page.meta_description and _overlap(page.title, page.meta_description) > 10:
        score += 1
    # Pas de keyword stuffing grossier (title != H1 exact)
    if page.title != page.h1:
        score += 1
    return min(5, score)


def _score_quality(page: CrawledPage) -> DimensionScore:
    """Score qualite editoriale (0-100)."""
    score = 50  # Base neutre
    issues = []
    strengths = []
    weaknesses = []

    # Longueur suffisante
    if page.word_count >= 1500:
        score += 20
        strengths.append(f"Contenu long : {page.word_count} mots")
    elif page.word_count >= 800:
        score += 10
    elif page.word_count >= 300:
        score += 0
    else:
        score -= 15
        weaknesses.append(f"Contenu court : {page.word_count} mots (min 300 recommande)")

    # Ratio texte/HTML
    if page.text_html_ratio > 20:
        score += 10
        strengths.append("Bon ratio texte/HTML")
    elif page.text_html_ratio < 8:
        score -= 8
        weaknesses.append("Trop de code par rapport au contenu visible")

    # Auteur
    if page.author_detected:
        score += 8
        strengths.append(f"Auteur identifie : {page.author_name}")
    else:
        weaknesses.append("Auteur non identifie")
        issues.append({"type": "missing_author", "gravity": "moderate", "fix": "Ajouter un auteur avec bio"})

    # Dates
    if page.date_published and _RE_NUMBER.search(page.date_published):
        score += 5
    elif page.date_modified:
        score += 3
    else:
        weaknesses.append("Pas de date de publication")

    # Schema
    if page.json_ld_valid:
        score += 7
        strengths.append(f"Schema.org present : {page.json_ld_types}")
    else:
        weaknesses.append("Pas de donnees structurees Schema.org")

    # CTA
    if page.has_cta:
        score += 5
        strengths.append(f"{page.cta_count} CTA detectes")
    else:
        weaknesses.append("Aucun CTA detecte")

    # Images
    if page.images_total > 0 and page.images_with_alt / page.images_total >= 0.8:
        score += 3
    elif page.images_total > 0 and page.images_with_alt == 0:
        weaknesses.append(f"{page.images_total} images sans attribut alt")

    score = max(0, min(100, score))
    return DimensionScore(score=score, max_score=100, issues=issues, strengths=strengths, weaknesses=weaknesses)


def _overlap(a: str, b: str, threshold: int = 3) -> int:
    """Mesure le chevauchement de mots entre deux textes."""
    wa = set(re.findall(r"\b\w{4,}\b", a.lower()))
    wb = set(re.findall(r"\b\w{4,}\b", b.lower()))
    if not wa or not wb:
        return 0
    return len(wa & wb)


_RE_NUMBER = re.compile(r"\d{4}")


async def run(state: AuditSessionState) -> AuditSessionState:
    """Score SEO On-Page + Qualite Editoriale pour chaque page."""
    state.current_agent = "ac02"

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        # Scores individuels
        title = _score_title(page)
        meta = _score_meta(page)
        h1 = _score_h1(page)
        hn = _score_hn(page)
        images = _score_images(page)
        links = _score_links(page)
        density = _score_density(page)
        coherence = _score_coherence(page)

        total_seo = title + meta + h1 + hn + images + links + density + coherence

        seo_issues = []
        seo_weaknesses = []
        if title < 12: seo_weaknesses.append(f"Title SEO faible ({title}/20)")
        if meta < 8: seo_weaknesses.append(f"Meta description faible ({meta}/15)")
        if h1 < 10: seo_weaknesses.append(f"H1 manquant ou multiple ({h1}/15)")
        if images < 5: seo_weaknesses.append(f"Images sous-optimisees ({images}/10)")
        if links < 5: seo_weaknesses.append(f"Maillage interne faible ({links}/10)")

        seo_score = DimensionScore(
            score=total_seo,
            max_score=100,
            issues=seo_issues,
            strengths=[f"Title ({title}/20)", f"Meta ({meta}/15)", f"Hn ({hn}/15)"],
            weaknesses=seo_weaknesses,
        )

        quality_score = _score_quality(page)

        # Agreger
        global_s = int(seo_score.score * 0.5 + quality_score.score * 0.5)

        state.scores[page.url] = AuditScores(
            seo_onpage=seo_score,
            quality=quality_score,
            global_score=global_s,
            global_confidence="indicatif",
        )

    state.updated_at = datetime.now()
    return state
