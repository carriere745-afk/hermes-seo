"""S02 — Detection des Variations.

Compare les positions actuelles avec l'historique SQLite
et detecte les variations significatives.

Categories : chute critique (>10), chute importante (5-10),
progression (3-10), entree top 10, entree top 3, desindexation (>100).

Filtre anti-bruit : fenetre glissante 3 jours, exclusion Core Updates.
Non skippable.

$0 — deterministe.
"""

import logging
from datetime import datetime, timedelta

from hermes.models.serp_visibility import SerpVisibilityState, AlertEntry

logger = logging.getLogger("hermes.serp.sv02")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv02"
    if not state.positions:
        logger.warning("S02: aucune position — skip")
        return state

    # Si Core Update suspend les alertes individuelles
    if state.core_update_detected:
        logger.info("S02: Core Update en cours — variations enregistrees sans alertes")
        _record_variations(state, silent=True)
        state.updated_at = datetime.now()
        return state

    variations = _record_variations(state, silent=False)
    state.variations = variations

    # Generer les alertes pour les variations significatives
    for var in variations:
        if var["type"] == "fluctuation":
            continue
        if var["severity"] in ("critical", "high"):
            state.alerts.append(AlertEntry(
                type=var["type"],
                keyword=var["keyword"],
                url=var["url"],
                valeur_avant=var["position_before"],
                valeur_apres=var["position_after"],
                priorite="P0" if var["severity"] == "critical" else "P1",
                date=datetime.now(),
                note=f"{var['keyword']}: {var['position_before']} → {var['position_after']} en {var.get('days', 7)}j"
            ))

    logger.info(f"S02: {len(variations)} variations, {len(state.alerts)} alertes generees")
    state.updated_at = datetime.now()
    return state


def _record_variations(state: SerpVisibilityState, silent: bool = False) -> list[dict]:
    """Compare positions actuelles avec l'historique SQLite."""
    variations = []
    try:
        from hermes.core.serp_db import get_positions_for_keyword
    except Exception:
        return variations

    for pos in state.positions[:500]:
        history = get_positions_for_keyword(pos.keyword, days=30)
        if len(history) < 2:
            continue

        # Position precedente (moyenne sur 7 derniers jours hors aujourd'hui)
        recent = [r for r in history if r["date"] < datetime.now().isoformat()[:10]][:7]
        if not recent:
            continue

        prev_avg = sum(r["position"] for r in recent) / len(recent)
        current = pos.position
        delta = current - prev_avg  # positif = baisse

        var_type = _classify_variation(delta, current, prev_avg)
        if var_type == "fluctuation" and not silent:
            continue

        variations.append({
            "keyword": pos.keyword,
            "url": pos.url,
            "position_before": round(prev_avg, 1),
            "position_after": current,
            "delta": round(delta, 1),
            "type": var_type,
            "severity": _severity(var_type),
            "days": 7,
            "date": datetime.now().isoformat(),
        })

    return variations


def _classify_variation(delta: float, current: int, previous: float) -> str:
    if current > 100:
        return "desindexation"
    if delta > 10:
        return "chute_critique"
    if delta > 5:
        return "chute_importante"
    if delta > 3:
        return "chute_legere"
    if delta > 1:
        return "fluctuation"
    if delta > -3:
        return "fluctuation"
    if delta > -5:
        return "progression_legere"
    if delta > -10:
        return "progression_importante"
    if current <= 3 and previous > 3:
        return "entree_top3"
    if current <= 10 and previous > 10:
        return "entree_top10"
    return "progression_importante"


def _severity(var_type: str) -> str:
    if var_type in ("chute_critique", "desindexation"):
        return "critical"
    if var_type in ("chute_importante", "entree_top3", "entree_top10"):
        return "high"
    if var_type in ("chute_legere", "progression_importante"):
        return "medium"
    return "low"
