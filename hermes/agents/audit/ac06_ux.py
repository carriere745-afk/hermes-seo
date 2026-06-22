"""AC06 — Scoring UX / Lisibilite.

Flesch francais via textstat, longueur phrases/paragraphes, CTA, coherence.
Deterministe. OSS : textstat (deja integre).
"""

from datetime import datetime

from hermes.models.audit import AuditSessionState, DimensionScore


def _score_flesch(text: str) -> int:
    """Score Flesch francais (0-30)."""
    try:
        import textstat
        textstat.set_lang("fr")
        score = textstat.flesch_reading_ease(text)
    except Exception:
        # Fallback ultra-basique
        import re
        words = len(re.findall(r"\b\w+\b", text))
        sentences = max(1, len(re.findall(r"[.!?]+", text)))
        avg_words = words / sentences
        score = max(0, 100 - avg_words * 2)

    if score > 70: return 30
    if score > 50: return 20
    if score > 30: return 10
    return 5


def _score_phrases(page) -> int:
    """Score longueur des phrases (0-20)."""
    # Proxy : ratio mots / H2 comme estimation de la densite
    if page.word_count == 0:
        return 0
    # Une page bien structuree a des H2 comme marqueurs de sections
    h2_count = len(page.h2_list)
    if h2_count == 0:
        return 5
    words_per_section = page.word_count / max(1, h2_count)
    if 100 <= words_per_section <= 400:
        return 20
    if 50 <= words_per_section <= 600:
        return 10
    return 5


def _score_paragraphes(page) -> int:
    """Score longueur des paragraphes (0-15)."""
    # Proxy : un bon ratio texte/HTML suggere des paragraphes bien structures
    if page.text_html_ratio > 15:
        return 15
    if page.text_html_ratio > 8:
        return 8
    return 3


def _score_cta(page) -> int:
    """Score presence CTA (0-15)."""
    score = 0
    if page.has_cta:
        score += 8
        if page.cta_count >= 2:
            score += 4
    if page.external_links > 0:
        score += 3  # Liens d'action potentiels
    return min(15, score)


def _score_coherence(page) -> int:
    """Score coherence H1/title/meta (0-10)."""
    score = 5
    # Title et H1 partagent du vocabulaire
    import re
    tw = set(re.findall(r"\b\w{4,}\b", page.title.lower()))
    hw = set(re.findall(r"\b\w{4,}\b", page.h1.lower()))
    overlap = len(tw & hw)
    if overlap >= 3: score += 3
    elif overlap >= 1: score += 1
    return min(10, score)


def _score_structure(page) -> int:
    """Score structure visuelle (0-10)."""
    score = 0
    if page.images_total >= 2: score += 2
    if page.has_breadcrumbs: score += 2
    if page.has_viewport: score += 3  # Responsive
    if len(page.h2_list) >= 3: score += 2
    return min(10, score)


async def run(state: AuditSessionState, pages_text: dict | None = None) -> AuditSessionState:
    """Score UX pour chaque page."""
    state.current_agent = "ac06"

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        # Obtenir le texte de la page (depuis le crawler ou passe en param)
        text = pages_text.get(page.url, "") if pages_text else ""
        if not text:
            # Fallback : on approxime avec les metadonnees
            text = f"{page.title}. {page.meta_description}. " + " ".join(page.h2_list)

        flesch = _score_flesch(text) if text else 10
        phrases = _score_phrases(page)
        paragraphes = _score_paragraphes(page)
        cta = _score_cta(page)
        coherence = _score_coherence(page)
        structure = _score_structure(page)

        total = flesch + phrases + paragraphes + cta + coherence + structure

        strengths = []
        weaknesses = []
        if flesch >= 20: strengths.append(f"Bonne lisibilite Flesch ({flesch}/30)")
        else: weaknesses.append(f"Lisibilite a ameliorer ({flesch}/30)")
        if cta < 8: weaknesses.append("CTA absent ou faible")
        if not page.has_viewport: weaknesses.append("Pas de viewport (non responsive)")
        if page.has_breadcrumbs: strengths.append("Fil d'Ariane present")

        state.scores[page.url].ux = DimensionScore(
            score=min(100, total),
            max_score=100,
            strengths=strengths,
            weaknesses=weaknesses,
        )

    state.updated_at = datetime.now()
    return state
