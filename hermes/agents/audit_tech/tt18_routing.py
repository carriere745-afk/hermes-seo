"""T18 — Routage Inter-Pipelines.

Transmet les resultats de l'audit technique aux autres pipelines :
- Pipeline 2 (Audit Contenu) : pages thin content, structure faible
- Pipeline 4 (SERP Positions) : pages indexees/desindexees
- Pipeline 5 (Strategie) : silos fantomes, gaps structurels
- Pipeline 6 (Maillage Backlinks) : carte liens internes, orphelines
- Pipeline 7 (Maintenance) : CWV degrades, erreurs recurrentes

Format JSON structure pour chaque pipeline cible.
$0 — deterministe.
"""

import logging
from datetime import datetime

from hermes.models.audit_tech import TechAuditState

logger = logging.getLogger("hermes.audit_tech.tt18")


async def run(state: TechAuditState) -> TechAuditState:
    state.current_agent = "tt18"

    pipelines = []

    # Pipeline 2 — Audit Contenu : thin content + structure faible
    thin_content = [i for i in state.issues if i.category == "content" and "court" in i.description.lower()]
    structure_weak = [i for i in state.issues if i.category == "structure"]
    if thin_content or structure_weak:
        pipelines.append({
            "pipeline_id": 2,
            "pipeline_name": "Audit de Contenu",
            "data_type": "pages_to_rewrite",
            "urls": list(set(i.url for i in (thin_content + structure_weak) if i.url.startswith("http"))),
            "priority": "High",
            "note": f"{len(thin_content)} pages thin content, {len(structure_weak)} problemes structurels",
        })

    # Pipeline 4 — SERP Positions : pages indexees/desindexees
    index_issues = [i for i in state.issues if i.category == "indexation"]
    if index_issues:
        pipelines.append({
            "pipeline_id": 4,
            "pipeline_name": "SERP & Positions",
            "data_type": "indexation_changes",
            "urls": list(set(i.url for i in index_issues if i.url.startswith("http"))),
            "priority": "High",
            "note": f"{len(index_issues)} changements d'indexation",
        })

    # Pipeline 5 — Strategie : silos fantomes
    if state.silos_fantomes:
        urls = []
        for silo in state.silos_fantomes:
            urls.extend(silo.get("members", [])[:3])
        pipelines.append({
            "pipeline_id": 5,
            "pipeline_name": "Strategie",
            "data_type": "phantom_silos",
            "urls": urls,
            "priority": "Medium",
            "note": f"{len(state.silos_fantomes)} silos fantomes — creer des pages hub",
        })

    # Pipeline 6 — Maillage Backlinks : orphelines + carte liens
    if state.orphans or state.graph_edges:
        pipelines.append({
            "pipeline_id": 6,
            "pipeline_name": "Maillage & Backlinks",
            "data_type": "internal_link_map",
            "urls": state.orphans[:50] if state.orphans else [],
            "priority": "Medium" if len(state.orphans) > 5 else "Low",
            "note": f"{len(state.orphans)} orphelines, {len(state.graph_edges)} edges",
        })

    # Pipeline 7 — Maintenance : CWV degrades
    perf_issues = [i for i in state.issues if i.category == "performance"]
    if perf_issues:
        pipelines.append({
            "pipeline_id": 7,
            "pipeline_name": "Maintenance",
            "data_type": "performance_degradation",
            "urls": list(set(i.url for i in perf_issues if i.url.startswith("http"))),
            "priority": "Medium",
            "note": f"{len(perf_issues)} problemes de performance a surveiller",
        })

    state.pipelines_to_trigger = pipelines
    logger.info(f"T18: routing to {len(pipelines)} pipelines")
    state.updated_at = datetime.now()
    return state
