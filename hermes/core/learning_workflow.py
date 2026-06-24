"""Workflow P8 — Learning Engine."""

import logging
from datetime import datetime
from langgraph.graph import StateGraph, END
from hermes.agents.learning import LEARNING_REGISTRY, LEARNING_ORDER
from hermes.models.project import Project

logger = logging.getLogger("hermes.learning.workflow")


def build_learning_graph() -> StateGraph:
    graph = StateGraph(Project)
    for agent_id in LEARNING_ORDER:
        if agent_id in LEARNING_REGISTRY:
            graph.add_node(agent_id, LEARNING_REGISTRY[agent_id])
    if LEARNING_ORDER:
        graph.set_entry_point(LEARNING_ORDER[0])
    for i, aid in enumerate(LEARNING_ORDER):
        if i + 1 < len(LEARNING_ORDER):
            nid = LEARNING_ORDER[i + 1]
            graph.add_edge(aid, nid if nid in LEARNING_REGISTRY else END)
        else:
            graph.add_edge(aid, END)
    return graph.compile()


async def run_learning_pipeline(project: Project) -> Project:
    logger.info(f"P8: project={project.id}")
    try:
        graph = build_learning_graph()
        config = {"configurable": {"thread_id": project.id}}
        final = await graph.ainvoke(project, config)
        result = Project(**final) if isinstance(final, dict) else final
    except Exception as e:
        logger.error(f"P8: workflow failed: {e}")
        project.errors = getattr(project, 'errors', []) + [str(e)] if hasattr(project, 'errors') else [str(e)]
        return project
    result.updated_at = datetime.now()
    return result
