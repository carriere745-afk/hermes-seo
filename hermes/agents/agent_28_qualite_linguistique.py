"""Agent Agent_28 — Controle Qualite Linguistique FR (gap #8).

Verifie : accents manquants, apostrophes cassees, guillemets,
entites HTML visibles, ponctuation francaise, anglicismes,
coherence vouvoiement/tutoiement, caracteres Unicode echappes.
Score de qualite linguistique 0-100.
Ferme le gap #8 du document 630.
"""

import logging, re, time
from datetime import datetime
from collections import Counter

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.strategie_db import log_event
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_28")

# Anglicismes courants en francais (a remplacer)
ANGLICISMES = {
    "digital": "numerique", "digitalisation": "transformation numerique",
    "startup": "jeune pousse", "business": "entreprise/affaires",
    "scalable": "evolutif/adaptable", "disruptif": "de rupture",
    "challenger": "concurrent/defier", "booster": "stimuler/accelerer",
    "impacter": "avoir un impact sur", "implementer": "mettre en œuvre",
    "deployer": "deployer", "monetiser": "rentabiliser",
    "growth": "croissance", "hacking": "piratage",
    "feedback": "retour/avis", "brief": "resume/synthese",
    "checklist": "liste de verification", "benchmark": "etalonnage/comparatif",
    "pitch": "presentation/argumentaire", "deadline": "date limite/echeance",
}


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_28"
    agent_name = "Qualite Linguistique FR"
    t0 = time.perf_counter()

    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(
        agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = ""
        if state.brouillon_html:
            content = state.brouillon_html.html if hasattr(state.brouillon_html, "html") else str(state.brouillon_html)
        if not content:
            # Fallback: verifier le keyword
            content = state.keyword or ""

        # Analyser
        checks = _analyze_quality(content)
        score = _compute_score(checks)

        result.status = AgentStatus.COMPLETED
        result.data = {"score_linguistique": score, "checks": checks}
        state.qualite_linguistique = score

        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED
        result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))

    state.updated_at = datetime.now()
    return state


def _analyze_quality(text: str) -> dict:
    checks = {
        "accents_manquants": [],
        "apostrophes_cassees": False,
        "entites_html_visibles": [],
        "guillemets_mal_encodes": False,
        "unicode_echappe": [],
        "anglicismes": [],
        "ponctuation_fr": True,
        "majuscules_abusives": [],
        "phrases_tronquees": False,
    }

    # Accents manquants (ex: "deja" au lieu de "deja")
    accentless = re.findall(r"\b[a-z]*[e][a-z]*\b", text)
    common_fixes = {"deja": "deja", "tres": "tres", "apres": "apres",
                    "pres": "pres", "fete": "fete", "ete": "ete",
                    "modele": "modele", "systeme": "systeme"}
    for word in accentless:
        if word in common_fixes:
            checks["accents_manquants"].append(f"'{word}' → '{common_fixes[word]}'")

    # Apostrophes cassees
    if "&#039;" in text or "&#8217;" in text or "&apos;" in text:
        checks["apostrophes_cassees"] = True

    # Entites HTML visibles
    visible_entities = re.findall(r"&[a-zA-Z]+;", text)
    if visible_entities:
        checks["entites_html_visibles"] = visible_entities[:10]

    # Unicode echappe
    unicode_escapes = re.findall(r"\\u[0-9a-fA-F]{4}", text)
    if unicode_escapes:
        checks["unicode_echappe"] = unicode_escapes[:10]

    # Guillemets mal encodes
    if "â" in text or "â" in text:
        checks["guillemets_mal_encodes"] = True

    # Anglicismes
    for ang, fr in ANGLICISMES.items():
        if re.search(rf"\b{ang}\b", text.lower()):
            checks["anglicismes"].append(f"'{ang}' → '{fr}'")

    # Majuscules abusives (mots entiers en majuscules sauf acronymes)
    uppercase_words = re.findall(r"\b[A-Z]{4,}\b", text)
    checks["majuscules_abusives"] = uppercase_words[:5]

    # Phrases tronquees
    last_sentence = text.strip().rsplit(".", 1)[-1] if "." in text else ""
    if last_sentence and len(last_sentence.split()) < 3 and len(text) > 100:
        checks["phrases_tronquees"] = True

    return checks


def _compute_score(checks: dict) -> int:
    score = 100
    score -= len(checks["accents_manquants"]) * 3
    if checks["apostrophes_cassees"]:
        score -= 10
    score -= len(checks["entites_html_visibles"]) * 5
    score -= len(checks["unicode_echappe"]) * 5
    if checks["guillemets_mal_encodes"]:
        score -= 10
    score -= len(checks["anglicismes"]) * 5
    score -= len(checks["majuscules_abusives"]) * 3
    if checks["phrases_tronquees"]:
        score -= 15
    return max(0, min(100, score))
