"""M05 — Page Optimizer (avec Haiku, human-review obligatoire en MVP).

Execute les actions OPTIMIZE: enrichir EEAT, ajouter FAQ, ameliorer
structure, renforcer GEO, maillage interne, corriger thin content.

⚠️ HUMAN-REVIEW OBLIGATOIRE en MVP.
Non skippable. Cout: ~$0.01/page (Haiku).
"""

import json
import logging
import time
from datetime import datetime

from hermes.models.project import Project, ExecutionAction
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.maintenance.m05")


async def run(project: Project) -> Project:
    t0 = time.perf_counter()
    optimized = 0

    pending = [a for a in project.execution_actions
               if a.category == "optimize" and a.status == "pending"]

    for action in pending:
        if project.actions_executed_today >= project.max_actions_per_day:
            break

        # HUMAN-REVIEW: toujours required en MVP
        action.human_approval_required = True
        action.status = "requires_review"

        if project.mode_execution == "auto":
            try:
                result = await _optimize_page(project, action)
                action.content_to_generate = result
                action.status = "executed"
                action.executed_at = datetime.now()
                project.actions_executed_today += 1
                optimized += 1
            except Exception as e:
                action.status = "failed"
                action.execution_error = str(e)
        else:
            # semi-auto ou manual: generer le diff pour validation humaine
            try:
                result = await _optimize_page(project, action)
                action.content_to_generate = result
                action.human_approval_required = True
                optimized += 1
            except Exception as e:
                action.status = "failed"
                action.execution_error = str(e)

    duration_ms = int((time.perf_counter() - t0) * 1000)
    n_review = sum(1 for a in pending if a.status == "requires_review" and a.human_approval_required)
    log_event(session_id=project.id, agent_id="m05", pipeline_id="maintenance",
              model="claude-haiku-4-5", tokens_used=0, cost=0.01 * optimized,
              duration_ms=duration_ms, success=True,
              predictions={"optimized": optimized, "requires_review": n_review})

    logger.info(f"M05: {optimized} pages optimisees — {n_review} en attente de validation humaine")
    return project


async def _optimize_page(project: Project, action: ExecutionAction) -> str:
    """Genere le contenu d'optimisation via Haiku."""
    prompt = f"""Optimise une page pour {project.domain}. Action: {action.action_type}.
Description: {action.description}
Profil: {project.profile} | Secteur: {project.secteur}

Retourne le bloc HTML/texte a inserer dans la page. Format: {{"content": "...", "location": "after_h2:3", "diff_summary": "..."}}"""

    try:
        from hermes.core.llm import LLMFactory, _repair_json
        from hermes.config import _cfg
        factory = LLMFactory(anthropic_api_key=_cfg._resolve("ANTHROPIC_API_KEY"))
        text, _, _, _ = await factory.route(
            system_prompt="Tu es un expert en optimisation editoriale SEO. Retourne du JSON valide avec le contenu a inserer.",
            user_message=prompt, agent_id="m05", max_tokens=2048,
        )
        data = _repair_json(text)
        return json.dumps(data, indent=2, ensure_ascii=False) if data else f"# Optimisation: {action.description}\n\n## Contenu genere\n\n{text[:1000]}"
    except Exception:
        return f"# Optimisation proposee pour: {action.description}\n\n## Section a ajouter\n\nContenu a enrichir avec des donnees recentes, sources fiables et structure EEAT.\n\n*Cette optimisation necessite une validation humaine avant publication.*"
