"""M03 — Execution Dispatcher (agent critique — 6h).

Reçoit les recommandations P1→P6 + M01/M02, résout les conflits,
calcule l'automation_score, transforme en ConsolidatedRecommendation
puis ExecutionAction avec catégorie/priorité.

Consulte L08 (failures) pour éviter les actions vouées à l'échec.
Non skippable. $0.
"""

import json
import logging
import time
from datetime import datetime
from collections import defaultdict

from hermes.models.project import Project, ExecutionAction, ConsolidatedRecommendation
from hermes.core.project_db import (
    insert_execution_action, insert_consolidated_recommendation,
    get_project, update_project_scores,
)
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.maintenance.m03")

# Conflits connus et leur resolution
CONFLICT_RULES = [
    {
        "pattern": {"a_action": "ajouter_faq", "b_action": "fusionner"},
        "resolution": "fusionner d'abord, puis optimiser",
        "winner": "b",
    },
    {
        "pattern": {"a_action": "corriger_canonical", "b_action": "creer_backlink"},
        "resolution": "corriger d'abord, puis backlink",
        "winner": "a",
    },
    {
        "pattern": {"a_action": "enrichir_eeat", "b_action": "rediriger"},
        "resolution": "rediriger — pas d'enrichissement sur une page a supprimer",
        "winner": "b",
    },
    {
        "pattern": {"a_action": "creer_pilier", "b_action": "creer_satellite"},
        "resolution": "creer pilier d'abord, satellite ensuite (dependance naturelle)",
        "winner": "a",
    },
]

# Automation score par type d'action
AUTOMATION_SCORES = {
    "generer_llms_txt": 100,
    "generer_sitemap": 100,
    "generer_schema_faq": 90,
    "generer_meta_description": 85,
    "generer_title": 85,
    "generer_disavow": 20,
    "ajouter_faq": 70,
    "enrichir_eeat": 50,
    "content_refresh": 45,
    "creer_article": 80,
    "creer_pilier": 75,
    "core_update_recovery": 60,
    "reedition": 45,
    "envoyer_email": 70,
    "publier_cms": 90,
}


async def run(project: Project) -> Project:
    t0 = time.perf_counter()

    # 1. Collecter toutes les recommandations en attente
    all_recs = _collect_all_recommendations(project)

    # 2. Résoudre les conflits
    resolved = _resolve_conflicts(all_recs)

    # 3. Consulter les échecs (L08)
    resolved = await _check_failures(resolved, project)

    # 4. Transformer en ConsolidatedRecommendation
    consolidated: list[ConsolidatedRecommendation] = []
    execution_actions: list[ExecutionAction] = []

    for rec in resolved[:50]:  # Limiter à 50 actions par cycle
        # Calculer l'automation score
        action_type = rec.get("action_type", "unknown")
        auto_score = AUTOMATION_SCORES.get(action_type, 50)

        # Déterminer la catégorie
        category = _map_to_category(action_type)

        # Créer la recommandation consolidée
        cons = ConsolidatedRecommendation(
            source_pipelines=rec.get("source_pipelines", []),
            source_agents=rec.get("source_agents", []),
            sujet=rec.get("sujet", rec.get("description", "")),
            description=rec.get("description", ""),
            action_concrete=rec.get("action_concrete", rec.get("description", "")),
            action_executable=action_type,
            priority=rec.get("priority", "P2"),
            effort_estime=rec.get("effort_estime", ""),
            cout_estime=rec.get("cout_estime", 0),
            impact_estime=rec.get("impact_estime", ""),
            confidence_score=rec.get("confidence_score", 50),
            requires_human=auto_score < project.human_approval_threshold,
            human_reason="Validation humaine requise (automation < seuil)" if auto_score < project.human_approval_threshold else "",
            disclaimers=_get_disclaimers(category, action_type),
        )
        consolidated.append(cons)
        insert_consolidated_recommendation({
            "id": cons.id, "project_id": project.id,
            "source_pipelines": cons.source_pipelines,
            "source_agents": cons.source_agents,
            "sujet": cons.sujet, "description": cons.description,
            "action_concrete": cons.action_concrete,
            "action_executable": cons.action_executable,
            "priority": cons.priority, "effort_estime": cons.effort_estime,
            "cout_estime": cons.cout_estime, "impact_estime": cons.impact_estime,
            "confidence_score": cons.confidence_score,
            "requires_human": cons.requires_human,
            "human_reason": cons.human_reason,
            "disclaimers": cons.disclaimers,
        })

        # Créer l'action d'exécution
        ex = ExecutionAction(
            source_pipeline=rec.get("source_pipelines", [""])[0] if rec.get("source_pipelines") else "unknown",
            source_agent=rec.get("source_agents", [""])[0] if rec.get("source_agents") else "unknown",
            source_recommandation_id=cons.id,
            category=category,
            action_type=action_type,
            description=cons.description,
            priority=cons.priority,
            target_url=rec.get("target_url", ""),
            target_page=rec.get("target_page", ""),
            confidence_before=cons.confidence_score,
            predicted_impact=cons.impact_estime,
            human_approval_required=cons.requires_human,
        )
        execution_actions.append(ex)

        insert_execution_action({
            "id": ex.id, "project_id": project.id,
            "source_pipeline": ex.source_pipeline,
            "source_agent": ex.source_agent,
            "source_recommandation_id": ex.source_recommandation_id,
            "category": ex.category, "action_type": ex.action_type,
            "description": ex.description,
            "status": ex.status if hasattr(ex, 'status') else "pending",
            "priority": ex.priority,
            "target_url": ex.target_url, "target_page": ex.target_page,
            "confidence_before": ex.confidence_before,
            "predicted_impact": ex.predicted_impact,
            "human_approval_required": ex.human_approval_required,
            "automation_score": auto_score,
            "created_at": datetime.now().isoformat(),
        })

    project.recommandations = consolidated
    project.execution_actions.extend(execution_actions)

    # Mettre à jour la prochaine action recommandée
    if execution_actions:
        top = execution_actions[0]
        project.next_action = f"{top.category}: {top.description[:80]}"
        project.next_pipeline = top.source_pipeline
        project.next_action_priority = top.priority

    project.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=project.id, agent_id="m03", pipeline_id="maintenance",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"actions_dispatched": len(execution_actions)})

    logger.info(f"M03: {len(consolidated)} recommandations consolidees → {len(execution_actions)} actions "
                f"(auto={sum(1 for e in execution_actions if not e.human_approval_required)})")
    return project


def _collect_all_recommendations(project: Project) -> list[dict]:
    """Collecte les recommandations de tous les pipelines + M01/M02."""
    recs = []

    # 1. Recommandations déjà dans le projet (P5, P6, M01, M02)
    for rec in project.recommandations:
        if hasattr(rec, 'model_dump'):
            recs.append(rec.model_dump())
        else:
            recs.append(rec)

    # 2. Execution actions existantes (M01, M02)
    for ex in project.execution_actions:
        if ex.status not in ("executed", "failed", "rolled_back"):
            d = ex.model_dump() if hasattr(ex, 'model_dump') else ex
            d["action_type"] = d.get("action_type", d.get("action_executable", "unknown"))
            d["source_agents"] = [d.get("source_agent", "m01")]
            d["source_pipelines"] = [d.get("source_pipeline", "maintenance")]
            recs.append(d)

    return recs


def _resolve_conflicts(recs: list[dict]) -> list[dict]:
    """Résout les conflits entre recommandations."""
    if len(recs) <= 1:
        return recs

    to_remove = set()
    for i, rec_a in enumerate(recs):
        for j, rec_b in enumerate(recs):
            if i >= j:
                continue
            a_type = rec_a.get("action_type", "")
            b_type = rec_b.get("action_type", "")

            for rule in CONFLICT_RULES:
                pat = rule["pattern"]
                if (pat["a_action"] in a_type and pat["b_action"] in b_type) or \
                   (pat["b_action"] in a_type and pat["a_action"] in b_type):
                    winner = rule["winner"]
                    if winner == "a":
                        to_remove.add(j)
                        rec_b["conflict_note"] = f"Supprime: {rule['resolution']}"
                    else:
                        to_remove.add(i)
                        rec_a["conflict_note"] = f"Supprime: {rule['resolution']}"

    return [r for idx, r in enumerate(recs) if idx not in to_remove]


async def _check_failures(recs: list[dict], project: Project) -> list[dict]:
    """Consulte L08 pour filtrer les actions vouées à l'échec."""
    try:
        from hermes.core.project_db import _get_conn
        conn = _get_conn()
        rows = conn.execute("SELECT * FROM failures WHERE occurrences >= 3").fetchall()
        conn.close()
        failures = [dict(r) for r in rows]

        for rec in recs:
            action_type = rec.get("action_type", "")
            for fail in failures:
                if fail["action_type"] in action_type:
                    do_not = json.loads(fail.get("do_not_recommend_if", "{}"))
                    if _matches_context(do_not, project):
                        rec["priority"] = "P3"
                        rec["confidence_score"] = max(10, rec.get("confidence_score", 50) - 30)
                        rec["warning"] = f"Pattern d'echec detecte: {fail.get('failure_reason', '')}"
    except Exception as e:
        logger.debug(f"M03: Failure check skipped ({e})")

    return recs


def _matches_context(conditions: dict, project: Project) -> bool:
    """Vérifie si le projet correspond aux conditions d'exclusion."""
    if conditions.get("secteur") and conditions["secteur"] != project.secteur:
        return False
    if conditions.get("profile") and conditions["profile"] != project.profile:
        return False
    return True


def _map_to_category(action_type: str) -> str:
    if any(w in action_type for w in ["generer", "creer_article", "creer_pilier"]):
        return "generate"
    if any(w in action_type for w in ["optimiser", "enrichir", "rafraichir", "content_refresh", "ajouter", "reedition"]):
        return "optimize"
    if any(w in action_type for w in ["publier", "disavow", "upload", "envoyer", "soumettre"]):
        return "publish"
    if any(w in action_type for w in ["monitor", "suivi", "impact"]):
        return "monitor"
    return "generate"


def _get_disclaimers(category: str, action_type: str) -> list[str]:
    disclaimers = ["non_substitution"]
    if category == "generate":
        disclaimers.append("ia_generated")
    if category in ("publish", "optimize") and "ymyl" in action_type.lower():
        disclaimers.append("ymyl")
    return disclaimers
