"""AC04 — Scoring GEO (Generative Engine Optimization).

Evalue la capacite du contenu a etre cite par les IA generatives.
Reutilise source_credibility.py. Deterministe (pas de LLM).
"""

from datetime import datetime

from hermes.core.source_credibility import classify_domain, YMYL_SECTEURS
from hermes.models.audit import AuditSessionState, DimensionScore


def _score_sources(page) -> int:
    """Score sources (0-30)."""
    score = 0
    # Compter les liens externes vers des domaines de qualite
    if page.internal_links > 0 and page.external_links > 0:
        score += 5  # Au moins 1 lien sortant
        if page.external_links >= 3:
            score += 10
    # Verifier si les domaines externes sont A ou B (source_credibility)
    # En pratique, on regarde le nombre de liens externes comme proxy
    if page.external_links >= 5:
        score += 5
    return min(30, score)


def _score_entites(page) -> int:
    """Score entites nommees (0-25)."""
    score = 10  # Base — difficile a mesurer sans NLP lourd
    # Proxy : les pages longues ont plus de chances d'avoir des entites
    if page.word_count >= 2000:
        score += 10
    elif page.word_count >= 1000:
        score += 5
    # Schema = entites structurees
    if page.json_ld_valid:
        score += 5
    return min(25, score)


def _score_citations(page) -> int:
    """Score phrases citables (0-25)."""
    score = 10  # Base
    # Une page avec des H2 en questions et des sections bien structurees
    # a plus de chances d'avoir des phrases citables
    if len(page.h2_list) >= 5:
        score += 5
    if len(page.h3_list) >= 8:
        score += 5
    # Auteur identifie = plus credible
    if page.author_detected:
        score += 3
    return min(25, score)


def _score_chunks(page) -> int:
    """Score chunks autonomes (0-20)."""
    score = 10  # Base
    if page.word_count >= 1500:
        score += 5
    if len(page.h2_list) >= 3:
        score += 3
    return min(20, score)


async def run(state: AuditSessionState) -> AuditSessionState:
    """Score GEO pour chaque page."""
    state.current_agent = "ac04"

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        sources = _score_sources(page)
        entites = _score_entites(page)
        citations = _score_citations(page)
        chunks = _score_chunks(page)

        total = sources + entites + citations + chunks

        strengths = []
        weaknesses = []
        if sources >= 20: strengths.append(f"Sources correctes ({sources}/30)")
        else: weaknesses.append(f"Sources insuffisantes ({sources}/30)")
        if entites >= 15: strengths.append(f"Entites nommees probables ({entites}/25)")
        else: weaknesses.append("Peu d'entites nommees detectees")
        if citations < 15: weaknesses.append("Peu de phrases citables")

        state.scores[page.url].geo = DimensionScore(
            score=min(100, total),
            max_score=100,
            strengths=strengths,
            weaknesses=weaknesses,
        )

        # Recalcul global
        s = state.scores[page.url]
        s.global_score = int(
            s.seo_onpage.score * 0.25 + s.quality.score * 0.20 +
            s.aeo.score * 0.15 + s.geo.score * 0.15 + s.eea_t.score * 0.10 + s.ux.score * 0.15
        )

    state.updated_at = datetime.now()
    return state
