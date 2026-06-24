"""B11 — Export & Routage.

Produit le rapport backlinks + exporte en HTML/JSON/CSV.
Route vers P1 (contenu a promouvoir), P5 (strategie), P7 (maintenance).
Non skippable. $0 — pas de LLM.
"""

import json
import logging
import time
from datetime import datetime

from hermes.models.backlinks import BacklinksState
from hermes.core.backlinks_db import get_db_stats, insert_campaign_result
from hermes.core.strategie_db import log_event, save_prediction

logger = logging.getLogger("hermes.backlinks.b11")


async def run(state: BacklinksState) -> BacklinksState:
    t0 = time.perf_counter()
    state.current_agent = "b11"
    state.phase = "export"

    # 1. Calculer les scores globaux
    state.authority_score = _compute_authority(state)
    state.link_profile_health = _compute_health(state)
    state.portfolio_diversity_score = _compute_diversity(state)

    # 2. Rapport HTML
    state.rapport_html = _build_html_report(state)

    # 3. Rapport JSON
    state.rapport_json = _build_json_export(state)

    # 4. Routage
    state.pipelines_to_trigger = _build_routing(state)

    # 5. Enregistrer les campaign_results pour B08 (collecte anticipee)
    for camp in state.campaigns:
        if camp.link_acquired:
            insert_campaign_result({
                "campaign_id": camp.id,
                "backlink_id": "",
                "acquisition_date": camp.acquired_date.isoformat() if camp.acquired_date else None,
                "cost": camp.cost_engaged,
                "link_type": "guest_post",
                "target_page": state.site_url,
            })

    state.status = "completed"
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="b11", pipeline_id="backlinks",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
    )

    logger.info(f"B11: Export — Auth={state.authority_score}/100, Health={state.link_profile_health}/100, "
                f"Routes={len(state.pipelines_to_trigger)}")
    return state


def _compute_authority(state: BacklinksState) -> int:
    if not state.referring_domains:
        return 30
    avg_dr = sum(d.domain_rating for d in state.referring_domains) / len(state.referring_domains)
    avg_topical = sum(d.topical_score for d in state.referring_domains) / len(state.referring_domains)
    n_domains = len(state.referring_domains)
    diversity_bonus = min(20, n_domains * 0.5)
    return min(100, int(avg_dr * 0.4 + avg_topical * 0.3 + diversity_bonus + 20))


def _compute_health(state: BacklinksState) -> int:
    n_toxic = len(state.toxic_domains)
    n_total = max(len(state.referring_domains), 1)
    toxicity_ratio = n_toxic / n_total
    anchor_risk = state.anchor_risk_score / 100
    health = (1 - toxicity_ratio) * (1 - anchor_risk * 0.5) * 100
    return max(0, min(100, int(health)))


def _compute_diversity(state: BacklinksState) -> int:
    domain_types = Counter()
    for d in state.referring_domains:
        domain_types[d.domain_type] += 1
    n_types = len(domain_types)
    return min(100, n_types * 15 + 10)

from collections import Counter


def _build_html_report(state: BacklinksState) -> str:
    recs_html = ""
    for r in state.recommandations[:15]:
        recs_html += f"<tr><td>{r.domaine_cible}</td><td>{r.type_action}</td><td>{r.priorite}</td><td>{r.cout_estime:.0f} euros</td><td>{r.delai_estime}</td><td>{r.confidence_score}/100</td></tr>"

    toxic_html = ""
    for t in state.toxic_domains[:10]:
        toxic_html += f"<tr><td>{t['domain']}</td><td>{t['toxicity_level']}</td><td>{', '.join(t.get('reasons',[]))}</td><td>{t.get('recommandation','')}</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Hermes SEO — Audit Backlinks {state.domain}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:0 auto;padding:2rem}}h1{{border-bottom:3px solid #1E88E5}}h2{{color:#1E88E5;margin-top:2rem}}table{{width:100%;border-collapse:collapse;margin:1rem 0}}th{{background:#1E88E5;color:#fff;padding:8px}}td{{padding:8px;border-bottom:1px solid #e2e8f0}}.card{{background:#f8fafc;border-radius:12px;padding:1.5rem;margin:1rem 0}}</style></head>
<body>
<h1>Audit Backlinks — {state.domain}</h1>
<p>Genere le {datetime.now().strftime('%d/%m/%Y')} | Session: {state.session_id}</p>
<div class="card"><h2>Scores</h2>
<p><strong>Authority Score:</strong> {state.authority_score}/100 | <strong>Link Profile Health:</strong> {state.link_profile_health}/100 | <strong>Portfolio Diversity:</strong> {state.portfolio_diversity_score}/100</p>
</div>
<h2>Recommandations ({len(state.recommandations)})</h2>
<table><tr><th>Domaine</th><th>Type</th><th>Priorite</th><th>Cout</th><th>Delai</th><th>Confiance</th></tr>{recs_html}</table>
<h2>Domaines suspects ({len(state.toxic_domains)})</h2>
<table><tr><th>Domaine</th><th>Niveau</th><th>Raisons</th><th>Recommandation</th></tr>{toxic_html}</table>
<h2>Profil d'ancres</h2>
{"".join(f'<p><strong>{k}:</strong> {v.get("current",0)}% (cible: {v.get("target",0)}%)</p>' for k,v in state.anchor_profile.get("deviations", {}).items())}
<footer style="margin-top:3rem;text-align:center;color:#999">Hermes SEO v3 · FC Solutions · {datetime.now().year}</footer>
</body></html>"""


def _build_json_export(state: BacklinksState) -> str:
    data = {
        "session_id": state.session_id, "domain": state.domain,
        "date": datetime.now().isoformat(),
        "scores": {"authority": state.authority_score, "health": state.link_profile_health, "diversity": state.portfolio_diversity_score},
        "backlinks_count": len(state.backlinks), "domains_count": len(state.referring_domains),
        "toxic_domains": len(state.toxic_domains),
        "recommandations": [r.model_dump() for r in state.recommandations],
        "anchor_profile": state.anchor_profile,
    }
    return json.dumps(data, indent=2, ensure_ascii=False, default=str)


def _build_routing(state: BacklinksState) -> list[dict]:
    routes = []
    for rec in state.recommandations:
        if rec.priorite in ("P0", "P1"):
            routes.append({"pipeline_cible": "P6", "action": rec.type_action,
                          "domaine": rec.domaine_cible, "priorite": rec.priorite})
    return routes
