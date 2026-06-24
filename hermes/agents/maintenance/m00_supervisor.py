"""M00 — Superviseur Maintenance.

Startup check, chargement projet, rate limiting, compteur partage.
Non skippable. $0.
"""

import logging
import time
from datetime import datetime

from hermes.models.project import Project
from hermes.core.project_db import get_project, create_project
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.maintenance.m00")


async def run(project: Project) -> Project:
    t0 = time.perf_counter()

    # 1. Verifier que le projet existe dans hermes.db
    existing = get_project(project_id=project.id)
    if not existing and project.site_url:
        project.id = create_project({
            "id": project.id,
            "nom": project.nom or project.domain,
            "site_url": project.site_url,
            "domain": project.domain,
            "profile": project.profile,
            "secteur": project.secteur,
            "competitors": project.competitors,
            "keywords_cibles": project.keywords_cibles,
            "budget_mensuel": project.budget_mensuel,
        })
        logger.info(f"M00: Projet cree: {project.id}")
    elif existing:
        project.nom = existing.get("nom", project.nom)
        project.onboarding_step = existing.get("onboarding_step", "welcome")
        project.onboarding_progress = existing.get("onboarding_progress", 0)

    # 2. Configurer le rate limiting
    if project.max_actions_per_day <= 0:
        project.max_actions_per_day = 20

    # Reset quotidien
    today = datetime.now().strftime("%Y-%m-%d")
    if not hasattr(project, '_last_reset_date'):
        project._last_reset_date = today
        project.actions_executed_today = 0
    if today != getattr(project, '_last_reset_date', ''):
        project.actions_executed_today = 0
        project._last_reset_date = today

    # 3. Verifier les pipelines disponibles
    pipelines_ok = True
    try:
        from pathlib import Path
        serp_db = Path("data/serp_visibility.db")
        if not serp_db.exists():
            logger.warning("M00: P4 data manquantes")
            pipelines_ok = False
    except Exception:
        pipelines_ok = False

    if project.status == "new":
        project.status = "active"

    project.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m00", pipeline_id="maintenance",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True)

    logger.info(f"M00: Projet {project.id} — mode={project.mode_execution}, "
                f"quota={project.actions_executed_today}/{project.max_actions_per_day}, P4={'OK' if pipelines_ok else 'manquant'}")
    return project
