"""T19 — Export Rapport.

Genere les exports :
- HTML (rapport complet, imprimable)
- JSON (donnees structurees)
- CSV (liste des issues)
- PDF (via weasyprint si installe)

$0 — deterministe.
"""

import json
import logging
from datetime import datetime

from hermes.models.audit_tech import TechAuditState

logger = logging.getLogger("hermes.audit_tech.tt19")


async def run(state: TechAuditState) -> TechAuditState:
    state.current_agent = "tt19"

    # Le rapport est generic a la demande dans l'UI (pages/audit_tech_page.py)
    # Ici on prepare les donnees structurees

    state.status = "completed"
    state.updated_at = datetime.now()
    logger.info(f"T19: export ready — {len(state.issues)} issues, {len(state.roadmap)} sprints, score={state.scores.global_score}")
    return state


def build_html_report(state: TechAuditState) -> str:
    """Genere un rapport HTML complet inline (compatible copier-coller Google Docs)."""
    def badge(severity):
        colors = {"critical": "#c62828", "high": "#e65100", "medium": "#f9a825", "low": "#2e7d32", "info": "#1565c0"}
        bg = {"critical": "#fce4ec", "high": "#fff3e0", "medium": "#fffde7", "low": "#e8f5e9", "info": "#e3f2fd"}
        return f'<span style="background:{bg.get(severity,"#eee")};color:{colors.get(severity,"#333")};padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">{severity.upper()}</span>'

    rows = ""
    for issue in state.issues[:50]:
        rows += f"""<tr>
            <td>{badge(issue.priority)}</td>
            <td>{issue.category}</td>
            <td>{issue.description[:120]}</td>
            <td style="font-size:12px">{issue.url[:50]}</td>
            <td>{badge(issue.severity)}</td>
            <td style="font-size:12px"><span style="color:{'#2e7d32' if issue.confidence == 'high' else '#e65100' if issue.confidence == 'low' else '#f9a825'}">{issue.confidence}</span></td>
            <td style="font-size:12px">{issue.effort}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8"><title>Audit Technique — {state.domain}</title>
<style>
body{{max-width:1100px;margin:40px auto;padding:20px;font-family:Arial,sans-serif;font-size:14px;line-height:1.6;color:#222}}
h1{{border-bottom:3px solid #1E88E5;padding-bottom:10px}}h2{{margin-top:30px;border-bottom:1px solid #ddd;padding-bottom:5px}}
table{{width:100%;border-collapse:collapse;margin:15px 0;font-size:13px}}
th{{background:#1E88E5;color:#fff;padding:8px 10px;text-align:left}}td{{padding:6px 10px;border:1px solid #ddd;vertical-align:top}}
tr:nth-child(even){{background:#f5f7fa}}
.note{{background:#e3f2fd;border-left:4px solid #1E88E5;padding:10px 15px;margin:10px 0;border-radius:3px}}
</style></head><body>
<h1>Rapport d'Audit Technique</h1>
<p>Site : <strong>{state.site_url}</strong> | CMS : <strong>{state.cms_detected or 'non detecte'}</strong> | Profil : <strong>{state.profile}</strong></p>
<p>Date : {datetime.now().strftime('%d/%m/%Y %H:%M')} | Mode : {state.mode} | Pages auditees : {len(state.crawled_pages)}</p>

<h2>Score Global : {state.scores.global_score}/100 <span style="color:{'#2e7d32' if state.scores.global_confidence == 'high' else '#e65100' if state.scores.global_confidence == 'low' else '#f9a825'}">({state.scores.global_confidence})</span></h2>

<h2>Scores par Dimension</h2>
<table>
<tr><th>Dimension</th><th>Score</th><th>Confiance</th><th>Issues</th><th>Critiques</th></tr>
""" + "".join(
    f"<tr><td>{d}</td><td>{getattr(state.scores, d).score}/100</td><td style=\"color:{'#2e7d32' if getattr(state.scores, d).confidence == 'high' else '#e65100'}\">{getattr(state.scores, d).confidence}</td><td>{getattr(state.scores, d).issues_count}</td><td>{getattr(state.scores, d).critical_count}</td></tr>"
    for d in ["crawlability", "indexation", "architecture", "structure", "content", "performance", "mobile", "structured_data", "international", "security", "maillage"]
) + """
</table>

<h2>Issues ({len(state.issues)})</h2>
<table><tr><th>Priorite</th><th>Categorie</th><th>Description</th><th>URL</th><th>Severite</th><th>Confiance</th><th>Effort</th></tr>
""" + rows + """
</table>

<h2>Roadmap</h2>
""" + "".join(
    f'<div class="note"><strong>{s["sprint"]}</strong> : {s["count"]} taches, ~{s["estimated_hours"]}h — Profils : {", ".join(s["targets"])}</div>'
    for s in (state.roadmap or [])
) + f"""
<p style="margin-top:40px;color:#aaa;font-size:11px;text-align:center">Hermes SEO v3 · Pipeline Audit Technique · Genere le {datetime.now().strftime('%d/%m/%Y')}</p>
</body></html>"""


def build_json_export(state: TechAuditState) -> str:
    """Export JSON structure."""
    return json.dumps({
        "site_url": state.site_url,
        "domain": state.domain,
        "cms": state.cms_detected,
        "audit_date": state.updated_at.isoformat(),
        "mode": state.mode,
        "profile": state.profile,
        "pages_audited": len(state.crawled_pages),
        "global_score": state.scores.global_score,
        "global_confidence": state.scores.global_confidence,
        "issues": [{
            "id": i.id, "category": i.category, "description": i.description,
            "url": i.url, "severity": i.severity, "priority": i.priority,
            "confidence": i.confidence, "impact_business": i.impact_business,
            "gain_potentiel": i.gain_potentiel, "effort": i.effort,
            "source_agent": i.source_agent, "observed": i.observed, "rule": i.rule,
        } for i in state.issues],
        "roadmap": state.roadmap,
        "pipelines_to_trigger": state.pipelines_to_trigger,
    }, indent=2, ensure_ascii=False, default=str)


def build_csv_export(state: TechAuditState) -> str:
    """Export CSV des issues."""
    header = "ID,Priorite,Categorie,Description,URL,Severite,Confiance,Impact,Gain,Effort\n"
    rows = ""
    for i in state.issues:
        desc = i.description.replace('"', '""')
        rows += f'"{i.id}","{i.priority}","{i.category}","{desc}","{i.url}","{i.severity}","{i.confidence}","{i.impact_business}","{i.gain_potentiel}","{i.effort}"\n'
    return header + rows
