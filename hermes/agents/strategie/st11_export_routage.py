"""ST11 — Export & Routage.

Produit les livrables finaux :
- Executive Summary CEO (1 page)
- Rapport HTML complet
- JSON enrichi (API + Observability)
- Routage vers P1, P2, P3, P6, P7

Non skippable. $0 — pas de LLM.
"""

import json
import logging
import time
from datetime import datetime

from hermes.models.strategie import (
    StrategieState, ExecutiveSummary,
)
from hermes.core.strategie_db import log_event, save_prediction, save_session_state

logger = logging.getLogger("hermes.strategie.st11")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st11"
    state.phase = "export"

    # 1. Executive Summary CEO
    state.executive_summary = _build_executive_summary(state)

    # 2. Rapport HTML
    state.rapport_html = _build_html_report(state)

    # 3. Rapport JSON
    state.rapport_json = _build_json_export(state)

    # 4. Routage vers les pipelines d'execution
    state.pipelines_to_trigger = _build_routing(state)

    # 5. Sauvegarder la session
    try:
        save_session_state(
            session_id=state.session_id,
            state_json=state.model_dump_json(),
            status="completed",
            phase="export",
            current_agent="st11",
            recs=len(state.recommandations),
            kills=len(state.kill_list),
            health=state.executive_summary.sante_strategique,
            site_url=state.site_url,
            domain=state.domain,
            mode=state.mode,
        )
    except Exception as e:
        logger.error(f"ST11: Failed to save session: {e}")

    state.status = "completed"
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st11", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
        predictions={"routes": len(state.pipelines_to_trigger)},
    )

    # Log predictions for observability
    for rec in state.recommandations[:20]:
        if rec.priorite != "KILL":
            save_prediction(
                session_id=state.session_id, agent_id="st11",
                action_type=rec.action,
                keyword=rec.keywords[0] if rec.keywords else "",
                predicted_traffic=rec.trafic_estime,
                predicted_leads=rec.leads_estimes,
                predicted_roi=rec.roi_12mois,
                confidence=float(rec.confidence_score),
            )

    logger.info(f"ST11: Export complete — CEO Summary health={state.executive_summary.sante_strategique}/100, "
                f"{len(state.pipelines_to_trigger)} pipelines triggers")
    return state


def _build_executive_summary(state: StrategieState) -> ExecutiveSummary:
    # Sante strategique : moyenne des scores business ponderee par la faisabilite
    if state.business_scores:
        avg_business = sum(state.business_scores.values()) / len(state.business_scores)
        avg_feasibility = sum(state.feasibility_scores.values()) / max(len(state.feasibility_scores), 1)
        avg_ta = sum(state.topical_authority_scores.values()) / max(len(state.topical_authority_scores), 1)
        sante = int((avg_business * 0.4 + avg_feasibility * 0.3 + avg_ta * 0.3))
    else:
        sante = 50

    # Top 3 opportunites
    top_opps = sorted(state.opportunites, key=lambda o: o.get("opportunite_score", 0), reverse=True)[:3]
    top_opportunites = []
    for opp in top_opps:
        top_opportunites.append({
            "sujet": opp.get("sujet", ""),
            "volume": opp.get("volume_total", 0),
            "score": opp.get("opportunite_score", 0),
            "action": f"Creer un {opp.get('type_page_recommande', 'article')}",
            "potentiel": f"+{int(opp.get('volume_total', 0) * 0.05)} visites/mois estimees",
        })

    # Top 2 menaces
    menaces = []
    critical_cannibs = [c for c in state.cannibalisations if c.get("gravite") == "critical"]
    if critical_cannibs:
        menaces.append({
            "type": "Cannibalisation critique",
            "sujets": [c.get("keyword", "") for c in critical_cannibs[:3]],
            "impact": "Perte de positions et dilution d'autorite",
        })
    low_feasibility = [(s, f) for s, f in state.feasibility_scores.items() if f < 30]
    if low_feasibility:
        menaces.append({
            "type": "Sujets non defendables",
            "sujets": [s for s, _ in low_feasibility[:3]],
            "impact": "Risque de perte de positions si attaque concurrente",
        })

    # ROI estime
    total_revenu = sum(r.roi_12mois for r in state.recommandations if r.roi_12mois > 0)
    total_cout = sum(r.cout_estime for r in state.recommandations if r.priorite != "KILL")
    roi_bas = max(0, total_revenu * 0.6)
    roi_haut = max(0, total_revenu * 1.2)

    # Budget mensuel recommande
    budget = total_cout / 12 if total_cout > 0 else 500
    budget = max(100, min(5000, budget))

    # Perte estimee si inaction
    perte_keywords = sum(1 for c in state.cannibalisations if c.get("gravite") in ("critical", "high"))
    if perte_keywords > 0:
        perte = f"Risque de perte de position sur {perte_keywords} mots-cles cles en {6 if perte_keywords <= 3 else 12} mois"
    else:
        perte = "Stagnation du trafic organique, perte progressive face aux concurrents actifs"

    # Recommandations cles
    p0_recs = [r.sujet for r in state.recommandations if r.priorite == "P0"]
    recos_cles = p0_recs[:3] if p0_recs else [
        f"Traiter les {len(state.opportunites)} opportunites identifiees",
        f"Resoudre les {len(state.cannibalisations)} cannibalisations detectees",
    ]

    return ExecutiveSummary(
        sante_strategique=sante,
        top_opportunites=top_opportunites,
        top_menaces=menaces,
        roi_12mois_bas=round(roi_bas, 0),
        roi_12mois_haut=round(roi_haut, 0),
        budget_mensuel_recommande=round(budget, 0),
        horizon_roadmap="12 mois",
        perte_estimee_si_inaction=perte,
        recommandations_cles=recos_cles,
    )


def _build_html_report(state: StrategieState) -> str:
    es = state.executive_summary
    recs_html = ""
    for r in state.recommandations[:20]:
        confidence_color = "#28a745" if r.confidence_score >= 80 else ("#fd7e14" if r.confidence_score >= 60 else "#dc3545")
        recs_html += f"""
        <tr>
            <td><strong>{r.sujet}</strong></td>
            <td><span style="background:{'#fce4ec' if r.priorite=='P0' else '#fff3e0' if r.priorite=='P1' else '#e8f5e9'};padding:2px 8px;border-radius:8px">{r.priorite}</span></td>
            <td>{r.volume_recherche}</td>
            <td style="color:{confidence_color};font-weight:600">{r.confidence_score}/100</td>
            <td>{r.effort_estime}</td>
            <td>{r.roi_12mois:+.0f} euros</td>
            <td>{r.pipeline_cible}</td>
        </tr>"""

    kills_html = ""
    for k in state.kill_list:
        kills_html += f"<tr><td>{k.sujet}</td><td>{k.categorie}</td><td>{k.raison}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Hermes SEO — Strategie {state.domain}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:0 auto;padding:2rem;color:#222}}
h1{{font-size:2rem;border-bottom:3px solid #2563eb;padding-bottom:0.5rem}}
h2{{font-size:1.4rem;margin-top:2rem;color:#2563eb}}
.score{{font-size:3rem;font-weight:700;text-align:center}}
.score-green{{color:#28a745}}.score-orange{{color:#fd7e14}}.score-red{{color:#dc3545}}
.card{{background:#f8fafc;border-radius:12px;padding:1.5rem;margin:1rem 0}}
table{{width:100%;border-collapse:collapse;margin:1rem 0}}
th{{background:#2563eb;color:#fff;padding:8px;text-align:left}}
td{{padding:8px;border-bottom:1px solid #e2e8f0}}
</style></head>
<body>
<h1>Strategie Editoriale — {state.domain}</h1>
<p>Genere le {datetime.now().strftime('%d/%m/%Y')} | Mode: {state.mode} | Session: {state.session_id}</p>

<div class="card">
<h2>Sante Strategique</h2>
<div class="score score-{'green' if es.sante_strategique >=70 else 'orange' if es.sante_strategique >=40 else 'red'}">{es.sante_strategique}/100</div>
<p>Horizon roadmap: {es.horizon_roadmap} | Budget mensuel recommande: {es.budget_mensuel_recommande:.0f} euros</p>
</div>

<div class="card">
<h2>Top 3 Opportunites</h2>
{"".join(f'<p><strong>{o["sujet"]}</strong> — Volume: {o["volume"]}/mois — {o.get("action","")} — {o.get("potentiel","")}</p>' for o in es.top_opportunites)}
</div>

<div class="card">
<h2>Top Menaces</h2>
{"".join(f'<p><strong>{m["type"]}</strong>: {m.get("impact","")}</p>' for m in es.top_menaces)}
</div>

<div class="card">
<h2>ROI estime 12 mois</h2>
<p>Fourchette: <strong>{es.roi_12mois_bas:.0f} euros — {es.roi_12mois_haut:.0f} euros</strong></p>
<p>{es.perte_estimee_si_inaction}</p>
</div>

<h2>Roadmap Editoriale ({len([r for r in state.recommandations if r.priorite!='KILL'])} recommandations)</h2>
<table><tr><th>Sujet</th><th>Priorite</th><th>Volume</th><th>Confiance</th><th>Effort</th><th>ROI 12m</th><th>Pipeline</th></tr>
{recs_html}</table>

<h2>Kill List ({len(state.kill_list)} sujets)</h2>
<table><tr><th>Sujet</th><th>Categorie</th><th>Raison</th></tr>{kills_html}</table>

<footer style="margin-top:3rem;text-align:center;color:#999">Hermes SEO v3 · FC Solutions · {datetime.now().year}</footer>
</body></html>"""


def _build_json_export(state: StrategieState) -> str:
    data = {
        "session_id": state.session_id,
        "domain": state.domain,
        "mode": state.mode,
        "date": datetime.now().isoformat(),
        "executive_summary": state.executive_summary.model_dump() if state.executive_summary else {},
        "recommandations": [r.model_dump() for r in state.recommandations],
        "kill_list": [k.model_dump() for k in state.kill_list],
        "forecast": [f.model_dump() for f in state.forecast],
        "portfolio_allocation": state.portfolio_allocation,
        "routes": state.pipelines_to_trigger,
    }
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _build_routing(state: StrategieState) -> list[dict]:
    routes = []
    for rec in state.recommandations:
        if rec.priorite in ("P0", "P1"):
            routes.append({
                "pipeline_cible": rec.pipeline_cible,
                "action": rec.action,
                "sujet": rec.sujet,
                "priorite": rec.priorite,
                "keywords": rec.keywords,
                "confidence": rec.confidence_score,
            })
    return routes
