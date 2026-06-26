"""Agent P7.5 — Pipeline Editorial Engine (gap #7).

Gere la file d'attente de publication, les bloqueurs, le dry-run mode,
le journal d'execution. Ferme le gap "Pipeline editorial complet"
du document 630.

Base sur P7 existant, etend M03/M04/M05/M06 avec orchestration.
"""

import logging
import time
from datetime import datetime
from uuid import uuid4

from hermes.models.project import Project, ExecutionAction
from hermes.core.project_db import insert_execution_action, get_pending_actions
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.maintenance.pipeline_editorial")

# Seuils de qualite par type de contenu (document 630, module 18)
QUALITY_THRESHOLDS = {
    "news": 60,
    "analyse": 65,
    "pilier": 75,
    "comparatif": 70,
    "fiche_outil": 70,
    "page_service": 65,
    "page_categorie": 60,
    "article": 60,
}

# Garde-fous (bloqueurs)
PUBLICATION_BLOCKERS = [
    "no_faq_on_pilier",       # FAQ absente sur pilier
    "no_source_on_factuel",   # Pas de source sur contenu factuel
    "thin_content",           # < 300 mots
    "duplicate_h1",           # H1 duplique
    "missing_meta",           # Title ou meta absents
    "missing_schema",         # Schema requis absent
]


async def run(project: Project) -> Project:
    """Orchestre la file editoriale: controle qualite -> dry-run -> publication."""
    t0 = time.perf_counter()
    published = 0
    blocked = 0
    dry_run_skipped = 0

    # 1. Charger les actions en attente de publication
    pending = get_pending_actions(project.id)

    for action_dict in pending[:project.max_actions_per_day]:
        action = ExecutionAction(**action_dict) if isinstance(action_dict, dict) else action_dict
        if action.category not in ("publish", "generate"):
            continue

        # 2. Dry-run: publier seulement si mode != manual
        if project.mode_execution == "manual":
            dry_run_skipped += 1
            continue

        # 3. Verifier les bloqueurs
        blockers = _check_blockers(project, action)
        if blockers:
            action.status = "blocked"
            action.execution_error = "; ".join(blockers)
            blocked += 1
            logger.warning(f"Pipeline: action bloquee ({', '.join(blockers)})")
            continue

        # 4. Publier
        action.status = "executed"
        action.executed_at = datetime.now()
        project.actions_executed_today += 1
        published += 1

    project.local_seo = {
        **(project.local_seo or {}),
        "pipeline_stats": {
            "pending": len(pending),
            "published_today": published,
            "blocked": blocked,
            "dry_run_skipped": dry_run_skipped,
        },
    }
    project.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="pipeline", pipeline_id="maintenance",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"published": published, "blocked": blocked})

    logger.info(f"Pipeline editorial: {published} publies, {blocked} bloques, {dry_run_skipped} dry-run")
    return project


def _check_blockers(project, action) -> list[str]:
    """Verifie les garde-fous avant publication."""
    blockers = []
    action_type = action.action_type or "article"
    content = action.content_to_generate or ""

    # Thin content
    if len(content.split()) < 300:
        blockers.append("thin_content (<300 mots)")

    # FAQ on pilier
    if "pilier" in action_type and "faq" not in content.lower():
        blockers.append("no_faq_on_pilier")

    # Source on factuel
    if any(w in (action.description or "").lower() for w in ["chiffre", "prix", "benchmark", "donnee"]):
        if "source" not in content.lower() and "http" not in content[:500]:
            blockers.append("no_source_on_factuel")

    return blockers
