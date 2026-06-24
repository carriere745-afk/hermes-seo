"""Workflow P7 — Maintenance & Execution Engine."""

import logging
from datetime import datetime
from langgraph.graph import StateGraph, END
from hermes.agents.maintenance import MAINTENANCE_REGISTRY, MAINTENANCE_ORDER
from hermes.models.project import Project

logger = logging.getLogger("hermes.maintenance.workflow")


def build_maintenance_graph() -> StateGraph:
    graph = StateGraph(Project)
    for agent_id in MAINTENANCE_ORDER:
        if agent_id in MAINTENANCE_REGISTRY:
            graph.add_node(agent_id, MAINTENANCE_REGISTRY[agent_id])
    if MAINTENANCE_ORDER:
        graph.set_entry_point(MAINTENANCE_ORDER[0])
    for i, aid in enumerate(MAINTENANCE_ORDER):
        if i + 1 < len(MAINTENANCE_ORDER):
            nid = MAINTENANCE_ORDER[i + 1]
            graph.add_edge(aid, nid if nid in MAINTENANCE_REGISTRY else END)
        else:
            graph.add_edge(aid, END)
    return graph.compile()


async def run_maintenance_pipeline(project: Project) -> Project:
    logger.info(f"P7: project={project.id}, mode={project.mode_execution}")
    try:
        graph = build_maintenance_graph()
        config = {"configurable": {"thread_id": project.id}}
        final = await graph.ainvoke(project, config)
        result = Project(**final) if isinstance(final, dict) else final
    except Exception as e:
        logger.error(f"P7: workflow failed: {e}")
        project.errors = getattr(project, 'errors', []) + [str(e)] if hasattr(project, 'errors') else [str(e)]
        return project
    result.updated_at = datetime.now()
    return result
