"""Agent 28b — Linguistique FR Avancee (gap module 15 items #441-455).

Etend agent_28 avec:
- Ponctuation francaise (espace avant :;!?)
- Titres en majuscules entieres (sauf acronymes)
- Coherence vouvoiement/tutoiement
- Styles de date melanges (12/05/2026 vs 12 mai 2026)
- Nombres mal formates (1000 vs 1 000)
- Score qualite linguistique 0-100 ameliore (15 criteres)
"""

import re, logging, time
from datetime import datetime
from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_28b")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_28b"
    agent_name = "Linguistique FR Avancee"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        text = re.sub(r'<[^>]+>', ' ', content)  # Strip HTML

        checks = {
            "ponctuation_fr": _check_french_punctuation(text),
            "majuscules_abusives": _check_uppercase_abuse(text),
            "coherence_vouvoiement": _check_vouvoiement(text),
            "dates_melangees": _check_date_formats(text),
            "nombres_format": _check_number_formats(text),
            "phrases_trop_longues": _check_long_sentences(text),
            "repetitions_cta": _check_cta_repetition(content),
            "score": 0,
            "issues": [],
            "recommandations": [],
        }

        # Ponctuation francaise
        if checks["ponctuation_fr"]["missing_spaces"] > 0:
            checks["issues"].append(f"{checks['ponctuation_fr']['missing_spaces']} signes de ponctuation sans espace fine")
            checks["recommandations"].append("Ajouter une espace avant : ; ! ? en francais")

        # Majuscules
        if checks["majuscules_abusives"]["count"] > 0:
            checks["issues"].append(f"{checks['majuscules_abusives']['count']} mots en majuscules (hors acronymes)")
            checks["recommandations"].append("Remplacer les MAJUSCULES par du gras ou des minuscules")

        # Vouvoiement
        if checks["coherence_vouvoiement"]["mixed"]:
            checks["issues"].append("Melange vouvoiement/tutoiement detecte")
            checks["recommandations"].append("Uniformiser le vouvoiement sur tout le site")

        # Dates
        if checks["dates_melangees"]["mixed"]:
            checks["issues"].append("Formats de date melanges")
            checks["recommandations"].append("Utiliser un format de date uniforme (ex: 12 mai 2026)")

        # Nombres
        if checks["nombres_format"]["issues"] > 0:
            checks["issues"].append(f"{checks['nombres_format']['issues']} nombres sans separateur de milliers")
            checks["recommandations"].append("Ajouter une espace comme separateur de milliers (1 000, pas 1000)")

        # Phrases longues
        if checks["phrases_trop_longues"]["count"] > 0:
            checks["issues"].append(f"{checks['phrases_trop_longues']['count']} phrases >35 mots")
            checks["recommandations"].append("Couper les phrases trop longues (>35 mots)")

        # Score
        score = 100
        score -= checks["ponctuation_fr"]["missing_spaces"]
        score -= min(20, checks["majuscules_abusives"]["count"] * 3)
        if checks["coherence_vouvoiement"]["mixed"]: score -= 15
        if checks["dates_melangees"]["mixed"]: score -= 10
        score -= min(15, checks["nombres_format"]["issues"] * 2)
        score -= min(10, checks["phrases_trop_longues"]["count"] * 2)
        score -= checks.get("repetitions_cta", {}).get("penalty", 0)
        checks["score"] = max(0, min(100, score))

        result.status = AgentStatus.COMPLETED
        result.data = checks
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state


def _check_french_punctuation(text: str) -> dict:
    """Verifie les espaces avant la ponctuation francaise (: ; ! ?)."""
    missing = 0
    for char in [":", ";", "!", "?"]:
        # Il devrait y avoir une espace avant
        missing += len(re.findall(rf'\S\{char}', text))
        missing += len(re.findall(rf'\S\s\{char}', text))  # Espace mais pas fine
    return {"missing_spaces": min(20, missing)}


def _check_uppercase_abuse(text: str) -> dict:
    """Detecte les mots en majuscules entieres (sauf acronymes <4 lettres)."""
    words = re.findall(r'\b[A-ZÀ-Ü]{4,}\b', text)
    known_acronyms = {"HTML", "CSS", "SEO", "AEO", "GEO", "URL", "API", "CMS", "RGPD", "GDPR",
                      "JSON", "XML", "HTTP", "HTTPS", "SSL", "CWV", "LCP", "FCP", "CLS", "TTFB",
                      "GA4", "GSC", "PAA", "FAQ", "CTA", "ROI", "CTR", "SERP", "AI", "IA"}
    abusive = [w for w in words if w.upper() not in known_acronyms and len(w) > 3]
    return {"count": len(abusive), "examples": abusive[:5]}


def _check_vouvoiement(text: str) -> dict:
    """Detecte le melange vouvoiement/tutoiement."""
    vous = len(re.findall(r'\b(vous|votre|vos|votre)\b', text.lower()))
    tu = len(re.findall(r'\b(tu|ton|ta|tes|toi)\b', text.lower()))
    return {"vous_count": vous, "tu_count": tu, "mixed": vous > 0 and tu > 0, "dominant": "vous" if vous >= tu else "tu"}


def _check_date_formats(text: str) -> dict:
    """Detecte les formats de date melanges."""
    fr_dates = len(re.findall(r'\d{1,2}\s+(?:janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+\d{4}', text.lower()))
    num_dates = len(re.findall(r'\d{1,2}/\d{1,2}/\d{4}', text))
    iso_dates = len(re.findall(r'\d{4}-\d{2}-\d{2}', text))
    formats = sum(1 for x in [fr_dates, num_dates, iso_dates] if x > 0)
    return {"fr_dates": fr_dates, "num_dates": num_dates, "iso_dates": iso_dates, "mixed": formats > 1}


def _check_number_formats(text: str) -> dict:
    """Verifie les separateurs de milliers dans les grands nombres."""
    large = re.findall(r'\b\d{4,}\b', text)
    issues = sum(1 for n in large if int(n) >= 1000 and ' ' not in n)
    return {"numbers_found": len(large), "issues": min(20, issues)}


def _check_long_sentences(text: str) -> dict:
    """Detecte les phrases >35 mots."""
    sentences = re.findall(r'[^.!?]+[.!?]', text)
    long_sents = [s for s in sentences if len(s.split()) > 35]
    return {"count": len(long_sents), "examples": long_sents[:3]}


def _check_cta_repetition(content: str) -> dict:
    """Detecte les CTA repetes a l'identique."""
    ctas = re.findall(r'<a[^>]*>(.*?)</a>', content, re.IGNORECASE)
    seen = {}
    duplicates = 0
    for c in ctas:
        c_clean = c.strip().lower()[:50]
        if c_clean in seen:
            duplicates += 1
        seen[c_clean] = True
    return {"total_ctas": len(ctas), "duplicates": duplicates, "penalty": min(10, duplicates * 5)}
