"""ST06b — Forecast.

Projette le trafic et les leads sur 12 mois en fonction de la roadmap.
Utilise Claude Haiku pour l'analyse. Skippable en mode fast. Cout: ~$0.01.
"""

import json
import logging
import time
from datetime import datetime

from hermes.models.strategie import StrategieState, ForecastEntry
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st06b")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st06b"
    state.phase = "synthese"

    if state.mode == "fast":
        logger.info("ST06b: Skipped (mode fast)")
        state.updated_at = datetime.now()
        return state

    forecast: list[ForecastEntry] = []

    # Projection basee sur les recommandations P0 et P1
    active_recs = [r for r in state.recommandations if r.priorite in ("P0", "P1", "P2")]
    if not active_recs:
        active_recs = state.recommandations[:10]

    # Calculer les projections mensuelles
    forecast = _compute_forecast(active_recs, state)

    # Enrichir avec LLM si possible
    try:
        forecast = await _enrich_forecast_with_llm(state, forecast)
    except Exception as e:
        logger.warning(f"ST06b: LLM enrichment failed ({e})")

    state.forecast = forecast
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st06b", pipeline_id="strategie",
        model="claude-haiku-4-5",
        tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    total_trafic_12m = sum(f.trafic_estime for f in forecast)
    logger.info(f"ST06b: Forecast 12 mois — {total_trafic_12m} visites cumulees projetees")
    return state


def _compute_forecast(active_recs: list, state: StrategieState) -> list[ForecastEntry]:
    """Calcule le forecast mensuel sans LLM."""
    entries = []
    cumul_cout = 0.0
    cumul_trafic = 0
    cumul_leads = 0
    cumul_revenu = 0.0

    for mois in range(1, 13):
        trafic_mois = 0
        leads_mois = 0
        revenu_mois = 0.0
        cout_mois = 0.0

        for rec in active_recs:
            # Decaler le demarrage selon la priorite
            if rec.priorite == "P0":
                start_month = 1
            elif rec.priorite == "P1":
                start_month = 3
            elif rec.priorite == "P2":
                start_month = 6
            else:
                start_month = 9

            if mois >= start_month:
                ramp = min(1.0, (mois - start_month + 1) / 4)  # Ramp-up sur 4 mois
                trafic_mois += int(rec.trafic_estime * ramp)
                leads_mois += int(rec.leads_estimes * ramp) if rec.leads_estimes else 0
                revenu_mois += (rec.roi_12mois / 12) * ramp if rec.roi_12mois > 0 else 0

            # Cout de creation au mois de demarrage
            if mois == start_month:
                cout_mois += rec.cout_estime

        cumul_trafic += trafic_mois
        cumul_leads += leads_mois
        cumul_revenu += revenu_mois
        cumul_cout += cout_mois

        entries.append(ForecastEntry(
            mois=mois,
            trafic_estime=trafic_mois,
            leads_estimes=leads_mois,
            revenu_estime=round(revenu_mois, 0),
            cout_estime=round(cout_mois, 0),
            cumul_roi=round(cumul_revenu - cumul_cout, 0),
        ))

    return entries


async def _enrich_forecast_with_llm(state: StrategieState, forecast: list[ForecastEntry]) -> list[ForecastEntry]:
    """Utilise Haiku pour ajuster les projections."""
    summary = [{
        "mois": f.mois,
        "trafic_estime": f.trafic_estime,
        "leads_estimes": f.leads_estimes,
        "cout_estime": f.cout_estime,
    } for f in forecast]

    prompt = f"""Voici une projection de trafic SEO sur 12 mois pour {state.domain}.
{json.dumps(summary, indent=2)}

Le site a {len(state.recommandations)} recommandations actives (P0-P2).
Est-ce que ces projections te semblent realistes ? Ajuste les chiffres si necessaire.

Retourne un JSON: {{"ajustements": [{{"mois": 1, "trafic_corrige": 100, "leads_corriges": 5}}]}}
Sois conservateur. Ne change pas plus de 20%."""

    try:
        from hermes.core.llm import LLMFactory, _repair_json
        from hermes.config import _cfg
        factory = LLMFactory(anthropic_api_key=_cfg._resolve("ANTHROPIC_API_KEY"))
        text, _, _, _ = await factory.route(
            system_prompt="Tu es un analyste SEO data-driven. Ajuste les projections de maniere realiste et conservatrice. JSON uniquement.",
            user_message=prompt,
            agent_id="st06b",
            max_tokens=1024,
        )
        data = _repair_json(text)
        ajustements = {a["mois"]: a for a in data.get("ajustements", [])}

        for f in forecast:
            if f.mois in ajustements:
                adj = ajustements[f.mois]
                if "trafic_corrige" in adj:
                    f.trafic_estime = adj["trafic_corrige"]
                if "leads_corriges" in adj:
                    f.leads_estimes = adj["leads_corriges"]
    except Exception:
        pass

    return forecast
