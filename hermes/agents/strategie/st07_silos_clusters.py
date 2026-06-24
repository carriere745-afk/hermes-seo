"""ST07 — Silos & Clusters.

Analyse la structure des silos : detecte les silos sans pilier,
les piliers sans satellites, et les clusters mal formes.
Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st07")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st07"
    state.phase = "analyse"

    analysis: list[dict] = []

    # Analyser chaque silo de la topical map
    for silo_entry in state.topical_map:
        silo_name = silo_entry.get("silo", "general")
        sujets_silo = silo_entry.get("sujets", [])
        n_couverts = silo_entry.get("sujets_couverts", 0)
        n_manquants = silo_entry.get("sujets_manquants", 0)
        volume_total = silo_entry.get("volume_total", 0)

        # Verifier presence d'un pilier
        a_pilier = _has_pilier(silo_name, state)
        a_satellites = n_couverts > 1

        issues = []
        if not a_pilier:
            issues.append("silo_sans_pilier")
        if not a_satellites and a_pilier:
            issues.append("pilier_sans_satellites")
        if n_couverts == 0 and n_manquants == 0:
            issues.append("silo_vide")

        analysis.append({
            "silo": silo_name,
            "volume_total": volume_total,
            "sujets_couverts": n_couverts,
            "sujets_manquants": n_manquants,
            "a_pilier": a_pilier,
            "a_satellites": a_satellites,
            "issues": issues,
            "topical_authority": state.topical_authority_scores.get(silo_name, 0),
            "recommandations": _recommandations_silo(issues, silo_name, a_pilier),
        })

    state.silos_analysis = analysis
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st07", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    n_issues = sum(1 for a in analysis if a["issues"])
    logger.info(f"ST07: {len(analysis)} silos analyses — {n_issues} avec anomalies")
    return state


def _has_pilier(silo_name: str, state: StrategieState) -> bool:
    """Verifie si un silo a une page pilier."""
    # Verifier dans les pages existantes
    for page in state.pages_existantes:
        page_silo = page.get("silo", "")
        page_type = page.get("type_page", "")
        if page_silo == silo_name and page_type == "pilier":
            return True
    # Verifier parmi les sujets couverts
    for sujet in state.sujets:
        if sujet.silo == silo_name and sujet.couvert and sujet.type_page == "pilier":
            return True
    return False


def _recommandations_silo(issues: list[str], silo_name: str, a_pilier: bool) -> list[str]:
    recos = []
    if "silo_sans_pilier" in issues:
        recos.append(f"Creer un pilier pour le silo '{silo_name}' (hub de contenu)")
    if "pilier_sans_satellites" in issues:
        recos.append(f"Ajouter des articles satellites au pilier '{silo_name}'")
    if "silo_vide" in issues:
        recos.append(f"Evaluer la pertinence du silo '{silo_name}'. Peut-etre a supprimer ou fusionner.")
    if not issues:
        recos.append(f"Silo '{silo_name}' bien structure — maintenir")
    return recos
