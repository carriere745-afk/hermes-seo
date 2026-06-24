"""ST01b — Topical Authority Score.

Calcule un score d'autorite topique 0-100 par silo.
Combine P2 (qualite contenu) + P3 (architecture) + P4 (positions).
Non skippable. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime
from pathlib import Path

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st01b")

# Poids des facteurs
W_P2_QUALITY = 0.30
W_P3_ARCHITECTURE = 0.25
W_P4_POSITIONS = 0.25
W_COUVERTURE = 0.20


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st01b"
    state.phase = "analyse"

    scores: dict[str, int] = {}

    # Donnees disponibles
    p2_available = state.pipelines_disponibles.get("p2", False)
    p3_available = state.pipelines_disponibles.get("p3", False)
    p4_available = state.pipelines_disponibles.get("p4", False)

    # Pour chaque silo de la topical map
    for silo_entry in state.topical_map:
        silo_name = silo_entry.get("silo", "general")
        sujets_silo = silo_entry.get("sujets", [])
        n_sujets = len(sujets_silo) or 1
        n_couverts = sum(1 for s in sujets_silo if s.get("couvert"))

        # 1. Qualite P2 (moyenne des scores de contenu)
        p2_score = _get_p2_silo_score(silo_name) if p2_available else 50

        # 2. Architecture P3 (profondeur, maillage)
        p3_score = _get_p3_silo_score(silo_name) if p3_available else 50

        # 3. Positions P4 (rang moyen)
        p4_score = _get_p4_silo_score(state, silo_name) if p4_available else 50

        # 4. Couverture (ratio couverts / total)
        couverture = n_couverts / max(n_sujets, 1)
        couverture_score = int(couverture * 100)

        # Score pondere
        raw = (W_P2_QUALITY * p2_score +
               W_P3_ARCHITECTURE * p3_score +
               W_P4_POSITIONS * p4_score +
               W_COUVERTURE * couverture_score)

        scores[silo_name] = min(100, max(0, int(raw)))

    # Appliquer aux sujets
    for sujet in state.sujets:
        if sujet.silo in scores:
            sujet.topical_authority = scores[sujet.silo]

    state.topical_authority_scores = scores
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st01b", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST01b: {len(scores)} silos scores — moyenne={sum(scores.values())//max(len(scores),1)}/100")
    return state


def _get_p2_silo_score(silo: str) -> int:
    try:
        db_path = Path("data/audit_contenu.db")
        if not db_path.exists():
            return 50
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT AVG(score_global) as avg_score FROM pages WHERE silo = ?",
            (silo,)).fetchone()
        conn.close()
        if row and row["avg_score"]:
            return min(100, int(row["avg_score"]))
        return 50
    except Exception:
        return 50


def _get_p3_silo_score(silo: str) -> int:
    try:
        db_path = Path("data/audit_technique.db")
        if not db_path.exists():
            return 50
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT AVG(score) as avg_score FROM pages WHERE silo = ?",
            (silo,)).fetchone()
        conn.close()
        if row and row["avg_score"]:
            return min(100, int(row["avg_score"]))
        return 50
    except Exception:
        return 50


def _get_p4_silo_score(state: StrategieState, silo: str) -> int:
    """Score base sur les positions moyennes des mots-cles du silo."""
    sujets_silo = [s for s in state.sujets if s.silo == silo]
    if not sujets_silo:
        return 50
    positions = [s.position_moyenne for s in sujets_silo if s.position_moyenne > 0]
    if not positions:
        return 50
    avg_pos = sum(positions) / len(positions)
    if avg_pos <= 3:
        return 95
    elif avg_pos <= 5:
        return 85
    elif avg_pos <= 10:
        return 70
    elif avg_pos <= 20:
        return 50
    elif avg_pos <= 50:
        return 30
    else:
        return 10
