"""ST04c — GEO Opportunity Mapping.

Identifie les sujets susceptibles d'etre cites par les IA (SGE, ChatGPT, Perplexity...).
Skippable en mode fast. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st04c")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st04c"
    state.phase = "analyse"

    # Skip en mode fast
    if state.mode == "fast":
        logger.info("ST04c: Skipped (mode fast)")
        state.updated_at = datetime.now()
        return state

    geo_opps: list[dict] = []

    for sujet in state.sujets:
        score = _compute_geo_score(sujet)
        if score > 40:
            geo_opps.append({
                "sujet": sujet.nom,
                "keywords": sujet.keywords,
                "geo_score": score,
                "type_opportunite": _geo_type(score),
                "recommandation": _geo_recommandation(score, sujet.nom),
            })

    # Trier par meilleur score
    geo_opps.sort(key=lambda o: o["geo_score"], reverse=True)

    for sujet in state.sujets:
        for gopp in geo_opps:
            if gopp["sujet"] == sujet.nom:
                sujet.geo_opportunity = gopp["geo_score"]
                break

    state.geo_opportunities = geo_opps
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st04c", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST04c: {len(geo_opps)} opportunites GEO identifiees")
    return state


def _compute_geo_score(sujet) -> int:
    """Score 0-100 de probabilite d'etre cite par les IA."""
    score = 30  # Base

    # Types d'intention favorables aux citations IA
    intention = sujet.intention if hasattr(sujet, 'intention') else "informative"
    if intention == "informative":
        score += 25
    elif intention == "comparative":
        score += 15

    # Definitions, guides, tutoriels = fort potentiel GEO
    nom = sujet.nom.lower() if hasattr(sujet, 'nom') else ""
    geo_keywords = ["definition", "comment", "pourquoi", "guide", "tutoriel",
                    "exemple", "astuce", "meilleur", "comparatif", "alternative"]
    for gkw in geo_keywords:
        if gkw in nom:
            score += 10
            break

    # Volume eleve = plus de chance d'etre cite
    vol = sujet.volume_total if hasattr(sujet, 'volume_total') else 0
    if vol > 5000:
        score += 15
    elif vol > 1000:
        score += 10

    # Silo technique/SAAS = GEO friendly
    silo = sujet.silo.lower() if hasattr(sujet, 'silo') else ""
    geo_silos = ["saas", "tech", "outils", "logiciel", "marketing", "seo"]
    if any(gs in silo for gs in geo_silos):
        score += 10

    return min(100, score)


def _geo_type(score: int) -> str:
    if score >= 80:
        return "Citation IA tres probable"
    elif score >= 60:
        return "Citation IA probable"
    return "Potentiel GEO modere"


def _geo_recommandation(score: int, sujet_nom: str) -> str:
    if score >= 80:
        return f"Creer un contenu structure (FAQ + definitions claires) pour maximiser les chances de citation IA sur '{sujet_nom}'"
    elif score >= 60:
        return f"Inclure des donnees chiffrees et des definitions precises dans '{sujet_nom}'"
    return f"Surveiller l'evolution GEO pour '{sujet_nom}'"
