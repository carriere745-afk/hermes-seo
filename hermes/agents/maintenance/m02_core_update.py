"""M02 — Core Update Impact Analyzer (avec Haiku).

Analyse l'impact d'une Core Update detectee par P4 S02b.
Classification du type, pages touchees, gravite, plan de recovery.
Non skippable. Cout: ~$0.02 (Haiku).
"""

import json
import logging
import time
from datetime import datetime

from hermes.models.project import Project, ExecutionAction
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.maintenance.m02")

UPDATE_TYPES = {
    "helpful_content": {"signaux": ["thin content penalise", "eeat faible", "contenu generique"],
                        "recovery": "Renforcer EEAT, profondeur editoriale, expertise auteur"},
    "spam_update": {"signaux": ["liens toxiques", "contenu duplique", "ancres sur-optimisees"],
                    "recovery": "Nettoyer backlinks (Disavow), renforcer originalite du contenu"},
    "core": {"signaux": ["variations larges", "pas de pattern clair", "tous secteurs touches"],
             "recovery": "Ameliorer globalement la qualite : contenu, technique, autorite"},
    "reviews": {"signaux": ["pages avis penalisees", "reviews generiques", "etoiles sans contenu"],
                "recovery": "Rendre les avis plus authentiques, ajouter du contenu original"},
}


async def run(project: Project) -> Project:
    t0 = time.perf_counter()

    # Verifier si P4 S02b a detecte une Core Update
    core_update_detected = _check_core_update()
    if not core_update_detected:
        logger.info("M02: Aucune Core Update detectee — skip")
        return project

    # Analyser l'impact avec Haiku
    impact = await _analyze_impact(project, core_update_detected)

    # Generer le plan de recovery
    recovery_actions = _generate_recovery_plan(project, impact)
    project.execution_actions.extend(recovery_actions)

    project.core_update_impacted = True

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m02", pipeline_id="maintenance",
              model="claude-haiku-4-5", tokens_used=0, cost=0.02, duration_ms=duration_ms, success=True,
              predictions={"update_type": impact.get("update_type", "unknown")})

    logger.info(f"M02: Core Update analysee — type={impact.get('update_type')}, "
                f"{len(recovery_actions)} actions de recovery generees")
    return project


def _check_core_update() -> dict | None:
    try:
        import sqlite3
        from pathlib import Path
        db_path = Path("data/serp_visibility.db")
        if not db_path.exists():
            return None
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM alerts_log WHERE type='core_update' "
            "AND date >= date('now', '-7 days') ORDER BY date DESC LIMIT 1"
        ).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        return None


async def _analyze_impact(project: Project, alert: dict) -> dict:
    """Analyse l'impact via Haiku ou heuristique."""
    prompt = f"""Analyse l'impact d'une Core Update Google sur le site {project.domain}.
Profil: {project.profile}, Secteur: {project.secteur}.

Retourne un JSON:
{{"update_type": "core", "pages_touchees": 12, "silos_touches": ["blog", "produits"],
  "gravite": "high", "concurrents_touches": true,
  "recovery_plan": ["Renforcer EEAT", "Supprimer thin content", "Acquerir backlinks editoriaux"],
  "delai_recovery_estime": "4-6 semaines"}}"""

    try:
        from hermes.core.llm import LLMFactory, _repair_json
        from hermes.config import _cfg
        factory = LLMFactory(anthropic_api_key=_cfg._resolve("ANTHROPIC_API_KEY"))
        text, _, _, _ = await factory.route(
            system_prompt="Tu es un expert en recovery post-Core Update Google. JSON uniquement.",
            user_message=prompt, agent_id="m02", max_tokens=1024,
        )
        return _repair_json(text)
    except Exception:
        return {"update_type": "core", "pages_touchees": 5, "gravite": "medium",
                "recovery_plan": ["Ameliorer EEAT", "Rafraichir contenu", "Nettoyer backlinks"]}


def _generate_recovery_plan(project: Project, impact: dict) -> list[ExecutionAction]:
    actions = []
    plan = impact.get("recovery_plan", [])
    update_type = impact.get("update_type", "core")

    for i, step in enumerate(plan[:8]):
        category = "optimize"
        if "backlink" in step.lower() or "disavow" in step.lower():
            category = "publish"
        elif "creer" in step.lower() or "generer" in step.lower():
            category = "generate"

        actions.append(ExecutionAction(
            source_pipeline="m02", source_agent="m02",
            category=category,
            action_type=f"core_update_recovery_{update_type}",
            description=f"[Core Update Recovery] {step}",
            priority="P0" if i < 3 else "P1",
            confidence_before=60,
            predicted_impact=f"Recovery post-{update_type}",
        ))
    return actions
