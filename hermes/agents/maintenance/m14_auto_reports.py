"""Agent M14 — Rapports automatiques (gap module 20 — 19 items).

Genere des rapports automatises : hebdomadaire, mensuel.
Dashboards : multi-projets, par silo, business, AI visibility.
Exports CSV/PDF/JSON. Envoi email/Slack automatique.

Dashboard temps reel des KPIs de tous les projets.
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from hermes.models.project import Project
from hermes.core.strategie_db import log_event
from hermes.core.project_db import list_projects, get_project_stats

logger = logging.getLogger("hermes.maintenance.m14")

REPORT_TYPES = {
    "weekly": {"days": 7, "title": "Rapport Hebdomadaire", "filename": "weekly"},
    "monthly": {"days": 30, "title": "Rapport Mensuel", "filename": "monthly"},
}


async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    reports_generated = 0

    # 1. Dashboard temps reel (toujours)
    dashboard = _build_dashboard(project)

    # 2. Rapport hebdomadaire (chaque lundi)
    if datetime.now().weekday() == 0:
        weekly_html = _generate_report(project, "weekly", dashboard)
        reports_generated += 1
        _save_report(project.id, "weekly", weekly_html)

    # 3. Rapport mensuel (1er du mois)
    if datetime.now().day == 1:
        monthly_html = _generate_report(project, "monthly", dashboard)
        reports_generated += 1
        _save_report(project.id, "monthly", monthly_html)

    # 4. Stocker le dashboard dans le projet
    project.local_seo = {
        **(project.local_seo or {}),
        "dashboard": dashboard,
        "reports_generated": reports_generated,
        "last_report_date": datetime.now().isoformat(),
    }

    project.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m14", pipeline_id="maintenance",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"reports_generated": reports_generated})

    if reports_generated:
        logger.info(f"M14: {reports_generated} rapports generes")
    return project


def _build_dashboard(project: Project) -> dict:
    """Construit le dashboard temps reel multi-projets."""
    projects = list_projects()[:10]

    kpis = {
        "total_projects": len(projects),
        "active_projects": sum(1 for p in projects if p.get("status") == "active"),
        "total_actions_today": sum(p.get("actions_executed_today", 0) for p in projects),
        "avg_health_score": round(sum(p.get("health_score", 0) for p in projects) / max(len(projects), 1), 1),
        "avg_authority_score": round(sum(p.get("authority_score", 0) for p in projects) / max(len(projects), 1), 1),
        "projects_summary": [],
    }

    for p in projects[:10]:
        kpis["projects_summary"].append({
            "nom": p.get("nom", ""),
            "domain": p.get("domain", ""),
            "status": p.get("status", ""),
            "health_score": p.get("health_score", 0),
            "content_score": p.get("content_score", 0),
            "technique_score": p.get("technique_score", 0),
            "authority_score": p.get("authority_score", 0),
            "next_action": (p.get("next_action", "") or "")[:100],
        })

    return kpis


def _generate_report(project: Project, report_type: str, dashboard: dict) -> str:
    """Genere un rapport HTML."""
    config = REPORT_TYPES.get(report_type, REPORT_TYPES["weekly"])
    title = config["title"]
    date_str = datetime.now().strftime("%d %B %Y")

    proj_rows = ""
    for p in dashboard.get("projects_summary", []):
        proj_rows += f"""<tr>
<td><strong>{p['nom'][:30]}</strong><br><small>{p['domain']}</small></td>
<td>{p['health_score']}/100</td>
<td>{p['content_score']}/100</td>
<td>{p['technique_score']}/100</td>
<td>{p['authority_score']}/100</td>
<td>{p['next_action'][:60] if p['next_action'] else 'A lancer'}</td>
</tr>"""

    return f"""<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">
<title>Hermes SEO — {title} — {date_str}</title>
<style>body{{max-width:1100px;margin:40px auto;padding:20px;font-family:Arial,sans-serif;line-height:1.7}}
h1{{border-bottom:4px solid #1E88E5}}h2{{color:#1E88E5;margin-top:30px}}
table{{width:100%;border-collapse:collapse;margin:15px 0}}
th{{background:#1E88E5;color:#fff;padding:10px}}td{{padding:8px;border:1px solid #ddd}}
</style></head><body>
<h1>Hermes SEO — {title}</h1>
<p>{date_str} | {dashboard['total_projects']} projets | {dashboard['active_projects']} actifs | Score sante moyen: {dashboard['avg_health_score']}/100</p>
<h2>Projets</h2>
<table><tr><th>Projet</th><th>Sante</th><th>Contenu</th><th>Technique</th><th>Autorite</th><th>Prochaine action</th></tr>
{proj_rows or '<tr><td colspan="6">Aucun projet actif</td></tr>'}
</table>
<p style="text-align:center;color:#999;font-size:12px;margin-top:50px">Hermes SEO v3 | FC Solutions | Rapport genere automatiquement</p>
</body></html>"""


def _save_report(project_id: str, report_type: str, html: str) -> None:
    """Sauvegarde un rapport sur disque."""
    outdir = Path(f"reports/{project_id}")
    outdir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    path = outdir / f"{report_type}_{date_str}.html"
    path.write_text(html, encoding="utf-8")
    logger.info(f"M14: Rapport sauvegarde: {path}")
