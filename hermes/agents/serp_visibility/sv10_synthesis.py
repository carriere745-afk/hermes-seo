"""S10 — Synthese & Rapport Hebdomadaire.

Produit le rapport hebdomadaire consolide :
- Score de sante SERP (0-100)
- Resume des variations
- Top Quick Wins avec Business Score
- AI Visibility Score + Share of Voice
- Routage vers les autres pipelines
- Rapport HTML

Non skippable.

$0 (+ Haiku pour resume en premium).
"""

import logging
from datetime import datetime

from hermes.models.serp_visibility import SerpVisibilityState

logger = logging.getLogger("hermes.serp.sv10")


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv10"

    # 1. Score de sante SERP (0-100)
    components = {}

    # Positions moyennes ponderees (25%)
    if state.positions:
        weighted_pos = sum(p.position * p.search_volume for p in state.positions[:50] if p.search_volume > 0)
        total_vol = sum(p.search_volume for p in state.positions[:50] if p.search_volume > 0) or 1
        avg_pos = weighted_pos / total_vol
        pos_score = max(0, 25 - int(avg_pos * 1.5))
    else:
        pos_score = 0
    components["positions"] = min(25, pos_score)

    # Tendance (15%) — variations positives = bonus
    positive_vars = sum(1 for v in (state.variations or []) if v.get("type", "").startswith("progression") or v.get("type", "").startswith("entree"))
    total_vars = max(1, len(state.variations or []))
    components["trend"] = int(positive_vars / total_vars * 15)

    # SERP features (10%)
    has_features = sum(1 for f in state.serp_features if f.present)
    total_features = max(1, len(state.serp_features))
    components["serp_features"] = int(has_features / total_features * 10)

    # AI Visibility (15%)
    components["ai_visibility"] = int(state.ai_visibility_score * 0.15)

    # Share of Voice (15%)
    components["sov"] = int(state.sov_score * 0.15)

    # Quick Wins actifs (10%)
    qw_total = max(1, len(state.quick_wins))
    qw_p1 = sum(1 for w in state.quick_wins if w.priorite == "P1")
    components["quick_wins"] = int(qw_p1 / qw_total * 10)

    # Correlations positives (10%)
    if state.correlations:
        pos_corr = sum(1 for c in state.correlations if c.confidence_score in ("High", "Medium"))
        components["correlations"] = int(pos_corr / max(1, len(state.correlations)) * 10)
    else:
        components["correlations"] = 0

    state.health_score = sum(components.values())

    # 2. Insights et encouragements (depuis les alertes S04/S07)
    encouragements_list = [a.note for a in state.alerts if a.type in ("opportunite_concurrentielle", "faisabilite_da")]

    # 3. Analyse du paysage concurrentiel (depuis S04)
    competitor_types = {}
    low_threat_count = 0
    for alert in state.alerts:
        if "faible menace" in alert.note.lower() or "opportunite" in alert.type:
            low_threat_count += 1

    # Generer un resume executif
    resume_lines = []
    if encouragements_list:
        resume_lines.append("### Opportunites detectees")
        for e in encouragements_list[:3]:
            resume_lines.append(f"- {e}")

    # Synthese du paysage concurrentiel
    if low_threat_count > 0:
        resume_lines.append(
            f"- Le paysage concurrentiel est favorable sur {low_threat_count} mots-cles — "
            f"peu de marques nationales, beaucoup d'annuaires/petits locaux"
        )

    # Recommendations basees sur les donnees
    if state.positions:
        top_positions = [p for p in state.positions if p.position <= 10]
        if top_positions:
            resume_lines.append(f"- {len(top_positions)} mots-cles deja dans le top 10 — proteger ces positions avec du contenu frais")
        near_top = [p for p in state.positions if 11 <= p.position <= 20]
        if near_top:
            resume_lines.append(f"- {len(near_top)} mots-cles en position 11-20 — Quick Wins potentiels avec enrichissement cible (P1)")

    if state.ai_visibility_score < 30 and state.mode != "fast":
        resume_lines.append(f"- AI Visibility faible ({state.ai_visibility_score}/100) — prioriser llms.txt, FAQ et sources (P3/P1)")

    state.resume_executif = resume_lines

    # 4. Routage inter-pipelines
    pipelines = []
    if state.quick_wins:
        urls_p1 = [w.url for w in state.quick_wins if w.pipeline_cible == "P1"][:10]
        if urls_p1:
            pipelines.append({"pipeline_id": 1, "pipeline_name": "Editorial", "data_type": "quick_wins", "urls": urls_p1, "priority": "High"})
    if state.content_gaps:
        pipelines.append({"pipeline_id": 1, "pipeline_name": "Editorial", "data_type": "content_gaps", "urls": [g["url"] for g in state.content_gaps], "priority": "High"})
    if hasattr(state, 'orphans') and state.orphans:
        pipelines.append({"pipeline_id": 6, "pipeline_name": "Maillage", "data_type": "orphans", "priority": "Medium"})

    state.pipelines_to_trigger = pipelines

    # 5. Rapport HTML
    state.rapport_html = _build_report_html(state)

    state.status = "completed"
    logger.info(f"S10: health_score={state.health_score}, pipelines_triggered={len(pipelines)}, status={state.status}")
    state.updated_at = datetime.now()
    return state


def _build_report_html(state: SerpVisibilityState) -> str:
    """Genere un rapport HTML synthetique."""
    top_gainers = [v for v in (state.variations or []) if v.get("type", "").startswith("progression") or v.get("type", "").startswith("entree")][:5]
    top_losers = [v for v in (state.variations or []) if "chute" in v.get("type", "") or v.get("type") == "desindexation"][:5]

    rows_gainers = "".join(
        f"<tr><td>{v['keyword']}</td><td>+{abs(v.get('delta',0))}</td><td>{v['position_after']}</td></tr>"
        for v in top_gainers
    )
    rows_losers = "".join(
        f"<tr><td>{v['keyword']}</td><td>-{abs(v.get('delta',0))}</td><td>{v['position_after']}</td></tr>"
        for v in top_losers
    )

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Rapport SERP — {state.domain}</title>
<style>body{{font-family:Arial;max-width:800px;margin:40px auto}}h1{{color:#1E88E5}}table{{width:100%;border-collapse:collapse}}th,td{{padding:8px;border:1px solid #ddd}}th{{background:#1E88E5;color:#fff}}</style></head>
<body>
<h1>Rapport SERP & Visibility — {state.domain}</h1>
<p>Date: {datetime.now().strftime('%d/%m/%Y')} | Mode: {state.mode} | Keywords: {len(state.keywords)}</p>
<h2>Sante SERP: {state.health_score}/100</h2>
<p>AI Visibility: {state.ai_visibility_score}/100 | Share of Voice: {state.sov_score}/100</p>
<h3>Top Progressions</h3><table><tr><th>Keyword</th><th>Gain</th><th>Position</th></tr>{rows_gainers}</table>
<h3>Top Regressions</h3><table><tr><th>Keyword</th><th>Perte</th><th>Position</th></tr>{rows_losers}</table>
<h3>Quick Wins</h3><ul>{"".join(f'<li>{w.keyword} (pos {w.position}, BS={w.business_score}) — {w.action_recommandee}</li>' for w in (state.quick_wins or [])[:10])}</ul>
<p style="color:#aaa;font-size:11px;margin-top:40px">Hermes SEO v3 · Pipeline 4 · SERP & Visibility Intelligence</p>
</body></html>"""
