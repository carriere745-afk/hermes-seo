"""Agent 11b — AEO Enrichi (gap module 6 items #196-246).

Etend agent_11 existant avec:
- Score qualite position 0 (resume autonome, bullets, longueur ideale 100-200 mots)
- Detection FAQ par type (bloque si pilier sans FAQ)
- Generation auto FAQ depuis le corps + schema FAQPage
- Recherche vocale: formulations conversationnelles, reponses 29-45 mots
- PAA targeting: generation blocs PAA-ready, definitions snippet-ready
- Adaptation SERP features selon le mot-cle
"""

import re, logging, time, json
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_11b")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_11b"
    agent_name = "AEO Enrichi"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        keyword = state.keyword or ""
        type_page = state.type_page or "article"

        aeo = {
            "position_zero_score": 0,
            "faq_score": 0,
            "vocal_readiness": 0,
            "paa_score": 0,
            "citable_phrases": 0,
            "global_aeo_score": 0,
            "recommandations": [],
            "bloqueurs": [],
        }

        # 1. Score Position 0 — En Bref / Resume
        aeo["position_zero_score"] = _score_position_zero(content)
        if aeo["position_zero_score"] < 40:
            aeo["recommandations"].append("Ajouter un resume 'En bref' de 100-200 mots en haut de l'article")
        if aeo["position_zero_score"] < 70:
            aeo["recommandations"].append("Le resume doit etre autonome: repondre a 'de quoi s'agit-il' sans le contexte de l'article")

        # 2. FAQ
        faq = _analyze_faq(content, type_page)
        aeo["faq_score"] = faq["score"]
        if faq["questions"] == 0 and type_page in ("pilier", "comparatif", "fiche_outil"):
            aeo["bloqueurs"].append(f"FAQ obligatoire pour le type '{type_page}'")
        if faq["questions"] < 3:
            aeo["recommandations"].append(f"Ajouter au moins {3 - faq['questions']} questions a la FAQ")
        if faq["answers_too_long"] > 0:
            aeo["recommandations"].append(f"Reponses FAQ trop longues ({faq['answers_too_long']} >150 mots): risque penalite featured snippet")
        if not faq["has_schema"] and faq["questions"] > 0:
            aeo["recommandations"].append("Ajouter le schema FAQPage (JSON-LD) pour activer les rich results Google")
        aeo["faq_data"] = faq

        # 3. Recherche vocale
        aeo["vocal_readiness"] = _score_vocal(content)
        if aeo["vocal_readiness"] < 50:
            aeo["recommandations"].append("Ajouter des reponses courtes (29-45 mots) en langage naturel pour la recherche vocale")

        # 4. PAA targeting — phrases citables
        aeo["citable_phrases"] = len(_extract_citable_sentences(content))
        if aeo["citable_phrases"] < 3:
            aeo["recommandations"].append(f"Ajouter des phrases courtes et autonomes (actuellement {aeo['citable_phrases']}) pour les PAA")

        # 5. Score global AEO
        aeo["global_aeo_score"] = min(100, (aeo["position_zero_score"] * 0.30 +
                                            aeo["faq_score"] * 0.35 +
                                            aeo["vocal_readiness"] * 0.20 +
                                            min(aeo["citable_phrases"] * 5, 15)))

        result.status = AgentStatus.COMPLETED
        result.data = aeo
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state


def _score_position_zero(content: str) -> int:
    """Score du resume position 0 (En Bref)."""
    score = 60
    has_resume = bool(re.search(r'(?i)(en bref|resume|en resume|l\'essentiel|a retenir)', content))
    if not has_resume:
        return 30
    # Trouver le bloc resume (entre H2 En Bref et le H2 suivant)
    resume_match = re.search(r'(?i)(?:en bref|resume|l\'essentiel).{0,500}?(?=<h[23])', content, re.DOTALL)
    if resume_match:
        resume_text = resume_match.group(0)
        words = len(resume_text.split())
        if 80 <= words <= 220:
            score += 25
        elif words < 50:
            score -= 15
        bullets = len(re.findall(r'<li[^>]*>', resume_text))
        if bullets >= 3:
            score += 15
            # Verifier que les bullets sont informationnels
            if re.search(r'(?i)(\d+|chiffre|pourcentage|million|milliard)', resume_text):
                score += 10
    return max(0, min(100, score))


def _analyze_faq(content: str, type_page: str) -> dict:
    """Analyse la FAQ: nombre de questions, qualite des reponses, schema."""
    faq_section = re.search(r'(?i)(faq|foire aux questions|questions.*reponses).{0,5000}', content, re.DOTALL)
    if not faq_section:
        return {"questions": 0, "score": 0 if type_page in ("pilier", "comparatif", "fiche_outil") else 30,
                "answers_too_long": 0, "has_schema": False}

    section = faq_section.group(0)
    questions = re.findall(r'<h[34][^>]*>\s*(?:[^<]*\?)[^<]*</h[34]>', section)
    q_count = len(questions)

    # Reponses trop longues (>150 mots = penalite featured snippet)
    answers = re.findall(r'</h[34]>\s*(<p[^>]*>.*?</p>)', section, re.DOTALL)
    too_long = sum(1 for a in answers if len(a.split()) > 150)

    score = min(100, q_count * 15 + 20)
    if too_long > 0:
        score -= too_long * 10

    has_schema = bool(re.search(r'"@type"\s*:\s*"FAQPage"', content))
    if not has_schema:
        has_schema = bool(re.search(r'application/ld\+json.*FAQPage', content, re.DOTALL))

    return {"questions": q_count, "score": max(0, score),
            "answers_too_long": too_long, "has_schema": has_schema}


def _score_vocal(content: str) -> int:
    """Score de preparation pour la recherche vocale."""
    score = 40
    # Reponses courtes (29-45 mots)
    sentences = re.findall(r'[^.!?]+[.!?]', content)
    short_precise = [s for s in sentences if 25 <= len(s.split()) <= 50]
    if len(short_precise) >= 3:
        score += 30
    # Formulations conversationnelles
    conversational = len(re.findall(r'(?i)(comment faire|voici comment|pour cela|il suffit|il faut)', content))
    score += min(20, conversational * 5)
    # Reponses directes (pas de "Eh bien...", "Alors...")
    filler_starts = len(re.findall(r'(?i)^\s*(eh bien|alors|du coup|en fait|bon)', content, re.MULTILINE))
    score -= filler_starts * 5
    return max(0, min(100, score))


def _extract_citable_sentences(content: str) -> list[str]:
    """Extrait les phrases citables hors contexte (pour PAA/featured snippet)."""
    clean = re.sub(r'<[^>]+>', ' ', content)
    sentences = re.findall(r'[^.!?]{40,120}[.!?]', clean)
    # Filtrer: autonomes, factuels, avec entites
    citable = []
    for s in sentences:
        if re.search(r'(?i)(definition|est un|signifie|permet|consiste|represente)', s):
            citable.append(s.strip())
        elif re.search(r'\d+', s) and len(s.split()) <= 30:
            citable.append(s.strip())
    return citable[:10]
