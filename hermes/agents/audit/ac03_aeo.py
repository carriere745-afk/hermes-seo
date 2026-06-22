"""AC03 — Scoring AEO (Answer Engine Optimization).

Evalue la capacite du contenu a apparaitre dans les moteurs de reponse IA.
Deterministe (pas de LLM). Fallback OSS : GEO Optimizer Skill.
"""

import re
from datetime import datetime

from hermes.models.audit import AuditSessionState, CrawledPage, DimensionScore


def _score_en_bref(page: CrawledPage, html: str = "") -> int:
    """Score 'En bref' / Position 0 (0-25)."""
    score = 0
    h2_lower = [h.lower() for h in page.h2_list]

    # Chercher un bloc "En bref", "Resume", "L'essentiel", "En resume"
    for marker in ("en bref", "resume", "l'essentiel", "en resume", "a retenir"):
        for h in h2_lower:
            if marker in h:
                score += 10
                break
        if score > 0:
            break

    # Verifier la presence de bullets (ul/li) apres le premier H2
    if score > 0 and html:
        # Chercher des bullets dans les 500 premieres lignes
        body_start = html.lower().find("<body")
        if body_start > 0:
            head_section = html[body_start:body_start + 3000]
            bullet_count = len(re.findall(r"<li[^>]*>", head_section))
            if bullet_count >= 3:
                score += 5
    return min(25, score)


def _score_h2_questions(page: CrawledPage) -> int:
    """Score H2 en questions (0-20)."""
    question_starters = ("comment", "pourquoi", "quoi", "quand", "quel", "quelle",
                         "quels", "quelles", "qui", "ou", "combien", "est-ce que")
    h2_count = len(page.h2_list)
    if h2_count == 0:
        return 0

    question_h2 = sum(
        1 for h in page.h2_list
        if "?" in h or h.lower().split(" ")[0] in question_starters if h.split()
    )
    ratio = question_h2 / h2_count
    if ratio >= 0.5:
        return 20
    if ratio >= 0.25:
        return 10
    return 5


def _score_faq(page: CrawledPage) -> int:
    """Score FAQ (0-30)."""
    score = 0
    h2_lower = [h.lower() for h in page.h2_list]
    h3_lower = [h.lower() for h in page.h3_list]

    # Detection FAQ dans H2 ou H3
    faq_in_h2 = any("faq" in h or "question" in h for h in h2_lower)
    faq_in_h3 = any("faq" in h or "question" in h for h in h3_lower)

    if faq_in_h2 or faq_in_h3:
        score += 10  # Present

        # Compter les questions (H3 avec "?" ou H3 consecutifs sous FAQ)
        faq_section_started = False
        question_count = 0
        for h in page.h3_list:
            h_lower = h.lower()
            if faq_in_h2 and not faq_section_started:
                for h2 in h2_lower:
                    if "faq" in h2 or "question" in h2:
                        faq_section_started = True
                        break
            if faq_section_started:
                if "?" in h or any(h_lower.startswith(w) for w in ("comment", "pourquoi", "quoi", "quel", "qui")):
                    question_count += 1

        if question_count >= 5:
            score += 8
        elif question_count >= 3:
            score += 4

    # Schema FAQPage
    if "FAQPage" in page.json_ld_types:
        score += 10

    return min(30, score)


def _score_definitions(page: CrawledPage) -> int:
    """Score definitions / glossaire (0-15)."""
    score = 0
    # Chercher des H3 "Definition", "Glossaire" ou patterns de definition
    definition_h3 = sum(
        1 for h in page.h3_list
        if any(w in h.lower() for w in ("definition", "glossaire", "terme", "concept"))
    )
    if definition_h3 >= 1:
        score += 8
    if "DefinedTerm" in page.json_ld_types:
        score += 3
    return min(15, score)


def _score_longueur_reponses(page: CrawledPage) -> int:
    """Score longueur des reponses (0-10)."""
    # Estimation : si FAQ presente et contenu > 800 mots, les reponses
    # ont probablement une bonne longueur
    score = 5  # Neutre
    if page.word_count >= 1500:
        score += 3
    if page.word_count >= 800:
        score += 2
    return min(10, score)


async def run(state: AuditSessionState, pages_html: dict | None = None) -> AuditSessionState:
    """Score AEO pour chaque page."""
    state.current_agent = "ac03"

    # OSS fallback : GEO Optimizer Skill
    try:
        import importlib
        if importlib.util.find_spec("geo_optimizer"):
            pass  # Could use GEO Optimizer Skill for AEO scoring
    except Exception:
        pass

    for page in state.crawled_pages:
        if page.fetch_error:
            continue

        html = pages_html.get(page.url, "") if pages_html else ""

        en_bref = _score_en_bref(page, html)
        h2_q = _score_h2_questions(page)
        faq = _score_faq(page)
        definitions = _score_definitions(page)
        reponses = _score_longueur_reponses(page)

        total = en_bref + h2_q + faq + definitions + reponses

        weaknesses = []
        strengths = []
        if en_bref < 10: weaknesses.append("Bloc 'En bref' absent ou faible")
        else: strengths.append(f"Bloc resume present ({en_bref}/25)")
        if h2_q < 10: weaknesses.append("Peu de H2 en questions")
        else: strengths.append(f"H2 en questions ({h2_q}/20)")
        if faq < 15: weaknesses.append("FAQ absente ou insuffisante")
        else: strengths.append(f"FAQ presente ({faq}/30)")
        if definitions < 8: weaknesses.append("Pas de definitions / glossaire")
        if page.json_ld_valid and "FAQPage" in page.json_ld_types:
            strengths.append("Schema FAQPage present")
        elif faq >= 10:
            weaknesses.append("FAQ presente mais pas de schema FAQPage")

        state.scores[page.url].aeo = DimensionScore(
            score=min(100, total),
            max_score=100,
            strengths=strengths,
            weaknesses=weaknesses,
        )

        # Recalculer le score global
        s = state.scores[page.url]
        s.global_score = int(
            s.seo_onpage.score * 0.30 + s.quality.score * 0.25 +
            s.aeo.score * 0.15 + s.global_score * 0.30
        )

    state.updated_at = datetime.now()
    return state
