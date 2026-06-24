"""ST05b — SEO Economics.

Calcule l'economie complete de chaque recommandation potentielle :
effort estime, cout, ROI a 12 mois, delai de resultats.

Skippable en mode fast. $0 — pas de LLM.
"""

import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st05b")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st05b"
    state.phase = "analyse"

    if state.mode == "fast":
        logger.info("ST05b: Skipped (mode fast)")
        state.updated_at = datetime.now()
        return state

    economics: list[dict] = []
    valeur_lead = state.valeur_lead
    taux_conversion = state.taux_conversion
    budget_mensuel = state.budget_mensuel or 500

    for sujet in state.sujets:
        volume = sujet.volume_total
        business_score = sujet.business_score
        feasibility = sujet.feasibility_score

        # Effort estime
        effort_h, cout = _estimate_effort(sujet)

        # Trafic estime (si bien positionne)
        ctr_estime = 0.05  # CTR moyen top 5
        trafic_mensuel = int(volume * ctr_estime)

        # Leads estimes
        leads_mensuels = trafic_mensuel * taux_conversion

        # ROI 12 mois
        # Mois 1-3: ramp-up (25% du trafic), Mois 4-6: 50%, Mois 7-12: 100%
        trafic_12m = (trafic_mensuel * 3 * 0.25) + (trafic_mensuel * 3 * 0.50) + (trafic_mensuel * 6 * 1.0)
        revenu_12m = trafic_12m * taux_conversion * valeur_lead
        cout_total = cout + (budget_mensuel * 0.1 * 12)  # Cout creation + 10% maintenance
        roi_12m = round(revenu_12m - cout_total, 0)

        # Delai estime
        delai = _estimate_delai(feasibility, volume)

        # Cout par lead
        cout_par_lead = round(cout_total / max(leads_mensuels * 12, 1), 1)

        economics.append({
            "sujet": sujet.nom,
            "volume_recherche": volume,
            "business_score": business_score,
            "feasibility_score": feasibility,
            "effort_estime": f"{effort_h}h",
            "effort_heures": effort_h,
            "cout_creation": cout,
            "trafic_mensuel_estime": trafic_mensuel,
            "leads_mensuels_estimes": round(leads_mensuels, 1),
            "revenu_12mois": round(revenu_12m, 0),
            "cout_total_12mois": round(cout_total, 0),
            "roi_12mois": roi_12m,
            "delai_resultats": delai,
            "cout_par_lead": cout_par_lead,
            "roi_positif": roi_12m > 0,
        })

    # Appliquer
    for sujet in state.sujets:
        for eco in economics:
            if eco["sujet"] == sujet.nom:
                sujet.effort_estime = eco["effort_estime"]
                sujet.cout_estime = eco["cout_creation"]
                sujet.roi_12mois = eco["roi_12mois"]
                sujet.delai_resultats = eco["delai_resultats"]
                break

    state.seo_economics = economics
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st05b", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    n_rentable = sum(1 for e in economics if e["roi_positif"])
    logger.info(f"ST05b: {len(economics)} sujets evalues — {n_rentable} rentables")
    return state


def _estimate_effort(sujet) -> tuple[int, float]:
    """Estime l'effort de creation en heures et cout associe."""
    type_page = sujet.type_page if hasattr(sujet, 'type_page') else "article"
    volume = sujet.volume_total if hasattr(sujet, 'volume_total') else 500

    base_effort = {
        "article": 4,
        "pilier": 8,
        "fiche_produit": 2,
        "faq": 3,
        "comparatif": 6,
        "landing": 5,
        "glossaire": 2,
        "service_local": 3,
    }
    heures = base_effort.get(type_page, 4)

    # Ajuster selon le volume
    if volume > 5000:
        heures += 3
    elif volume > 1000:
        heures += 1

    # Cout horaire estime 50 euros
    cout = heures * 50
    return heures, cout


def _estimate_delai(feasibility: int, volume: int) -> str:
    if feasibility >= 70:
        if volume <= 500:
            return "1-2 mois"
        elif volume <= 2000:
            return "2-4 mois"
        return "4-6 mois"
    elif feasibility >= 40:
        return "6-9 mois"
    return "9-12 mois"
