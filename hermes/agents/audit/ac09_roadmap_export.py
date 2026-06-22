"""AC09 — Roadmap + Export + Connecteur.

Classe les pages par priorite, genere la roadmap de reecriture,
prepare l'export et connecte au Pipeline Editorial.
Deterministe (pas de LLM).
"""

import json
from datetime import datetime

from hermes.models.audit import AuditSessionState


def _build_html_report(state: AuditSessionState) -> str:
    """Genere un rapport HTML d'audit."""
    total = len(state.crawled_pages)
    avg_score = int(
        sum(s.global_score for s in state.scores.values()) / max(1, len(state.scores))
    ) if state.scores else 0

    lines = [
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>",
        f"<title>Audit de Contenu — {state.site_url}</title>",
        "<style>body{font-family:Arial;max-width:900px;margin:auto;padding:20px}",
        "table{width:100%;border-collapse:collapse;margin:10px 0}",
        "th{background:#1E88E5;color:#fff;padding:10px}",
        "td{padding:8px;border:1px solid #ddd}",
        "tr:nth-child(even){background:#f5f7fa}",
        ".green{color:green}.orange{color:orange}.red{color:red}",
        "</style></head><body>",
        f"<h1>Audit de Contenu — {state.site_url}</h1>",
        f"<p>Date : {datetime.now().strftime('%d/%m/%Y')} | Pages auditees : {total} | Score moyen : {avg_score}/100</p>",
        "<h2>Scores par page</h2>",
        "<table><tr><th>URL</th><th>SEO</th><th>Qualite</th><th>AEO</th><th>GEO</th><th>EEAT</th><th>UX</th><th>Global</th><th>Action</th></tr>",
    ]

    for page in state.crawled_pages:
        if page.fetch_error:
            lines.append(f"<tr><td>{page.url}</td><td colspan='8' style='color:red'>Erreur: {page.fetch_error}</td></tr>")
            continue
        s = state.scores.get(page.url)
        brief = state.briefs.get(page.url)
        if not s:
            continue
        color = "green" if s.global_score >= 75 else ("orange" if s.global_score >= 50 else "red")
        action = brief.action if brief else "?"
        lines.append(
            f"<tr><td>{page.url[:60]}</td>"
            f"<td>{s.seo_onpage.score}</td>"
            f"<td>{s.quality.score}</td>"
            f"<td>{s.aeo.score}</td>"
            f"<td>{s.geo.score}</td>"
            f"<td>{s.eea_t.score}/16</td>"
            f"<td>{s.ux.score}</td>"
            f"<td class='{color}'><strong>{s.global_score}</strong></td>"
            f"<td>{action}</td></tr>"
        )

    lines.append("</table>")

    # Roadmap
    lines.append("<h2>Roadmap de Reecriture</h2><table><tr><th>Priorite</th><th>URL</th><th>Action</th><th>Score</th><th>Effort estime</th></tr>")
    for item in state.roadmap[:20]:
        lines.append(
            f"<tr><td>{item['priorite']}</td>"
            f"<td>{item['url'][:60]}</td>"
            f"<td>{item['action']}</td>"
            f"<td>{item['score']}</td>"
            f"<td>{item.get('effort', 'N/A')}</td></tr>"
        )
    lines.append("</table>")

    # Cannibalisation
    if state.cannibalisation:
        lines.append("<h2>Alertes Cannibalisation</h2><ul>")
        for c in state.cannibalisation:
            lines.append(f"<li>{c['page1'][:50]} ↔ {c['page2'][:50]} (similarite {c['similarite']}) → {c['action']}</li>")
        lines.append("</ul>")

    lines.append(f"<p style='color:#aaa;margin-top:30px'>Rapport genere par Hermes SEO v3 - {datetime.now().isoformat()}</p></body></html>")
    return "\n".join(lines)


async def run(state: AuditSessionState) -> AuditSessionState:
    """Roadmap + Export + Connecteur."""
    state.current_agent = "ac09"

    # Construire la roadmap
    roadmap = []
    for page in state.crawled_pages:
        if page.fetch_error:
            continue
        scores = state.scores.get(page.url)
        brief = state.briefs.get(page.url)
        if not scores or not brief:
            continue

        # Priorite basee sur score global + cannibalisation
        priority = 1 if scores.global_score < 50 else (2 if scores.global_score < 65 else 3)
        # Cannibalisation = priorite +1
        cannib = [c for c in state.cannibalisation if c["page1"] == page.url or c["page2"] == page.url]
        if cannib:
            priority = max(1, priority - 1)

        effort = "15 min" if page.word_count < 500 else ("30 min" if page.word_count < 1000 else "1h")
        roadmap.append({
            "url": page.url,
            "score": scores.global_score,
            "action": brief.action,
            "priorite": priority,
            "effort": effort,
            "cannibalisation": bool(cannib),
            "brief_id": page.url,
        })

    roadmap.sort(key=lambda x: (x["priorite"], x["score"]))
    state.roadmap = roadmap

    # Generer l'export HTML
    html_report = _build_html_report(state)

    # Rapport JSON
    json_report = {
        "site_url": state.site_url,
        "date": datetime.now().isoformat(),
        "total_pages": len(state.crawled_pages),
        "pages": [
            {
                "url": p.url,
                "scores": (state.scores.get(p.url).model_dump() if state.scores.get(p.url) else None),
                "brief": (state.briefs.get(p.url).model_dump() if state.briefs.get(p.url) else None),
            }
            for p in state.crawled_pages if not p.fetch_error
        ],
        "cannibalisation": state.cannibalisation,
        "roadmap": state.roadmap,
    }

    # CSV summary
    csv_lines = ["URL,SEO,Quality,AEO,GEO,EEAT,UX,Global,Action"]
    for page in state.crawled_pages:
        if page.fetch_error: continue
        s = state.scores.get(page.url)
        b = state.briefs.get(page.url)
        if not s: continue
        csv_lines.append(
            f"{page.url},{s.seo_onpage.score},{s.quality.score},{s.aeo.score},"
            f"{s.geo.score},{s.eea_t.score},{s.ux.score},{s.global_score},"
            f"{b.action if b else '?'}"
        )

    # Stocker dans la session (sera sauvegarde par SessionManager)
    state.status = "completed"
    state.updated_at = datetime.now()

    # Le connecteur (AC14 simplifie) : les briefs sont prets a etre consommes
    # par le Pipeline Editorial via state.briefs

    return state


def prepare_audit_brief_for_editorial(state: AuditSessionState, page_url: str) -> dict | None:
    """Helper : prepare un audit_brief pour le Pipeline Editorial.

    Cette fonction est le connecteur AC14 simplifie.
    Elle est appelee depuis l'UI quand l'utilisateur clique "Reecrire cette page".
    """
    brief = state.briefs.get(page_url)
    if not brief:
        return None
    return brief.model_dump()
