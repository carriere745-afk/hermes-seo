"""Workflow Pipeline 4 — SERP & Visibility Intelligence.

Orchestre les agents S00-S10 via LangGraph StateGraph.
Pattern identique aux pipelines 2 et 3.
"""

import logging
from datetime import datetime

from langgraph.graph import StateGraph, END

from hermes.agents.serp_visibility import SERP_REGISTRY, SERP_ORDER
from hermes.models.serp_visibility import SerpVisibilityState

logger = logging.getLogger("hermes.serp.workflow")


def build_serp_visibility_graph() -> StateGraph:
    graph = StateGraph(SerpVisibilityState)
    for agent_id in SERP_ORDER:
        if agent_id in SERP_REGISTRY:
            graph.add_node(agent_id, SERP_REGISTRY[agent_id])

    if SERP_ORDER:
        graph.set_entry_point(SERP_ORDER[0])

    for i, agent_id in enumerate(SERP_ORDER):
        if i + 1 < len(SERP_ORDER):
            next_id = SERP_ORDER[i + 1]
            if next_id in SERP_REGISTRY:
                graph.add_edge(agent_id, next_id)
            else:
                graph.add_edge(agent_id, END)
        else:
            graph.add_edge(agent_id, END)

    return graph.compile()


async def run_serp_pipeline(state: SerpVisibilityState) -> SerpVisibilityState:
    if not state.site_url:
        state.status = "error"
        logger.error("Pipeline 4: site_url requis")
        return state

    logger.info(f"Pipeline 4: {len(state.keywords)} keywords, site={state.domain}, mode={state.mode}")
    graph = build_serp_visibility_graph()
    config = {"configurable": {"thread_id": state.session_id}}
    final_state = await graph.ainvoke(state, config)

    if isinstance(final_state, dict):
        result = SerpVisibilityState(**final_state)
    else:
        result = final_state

    result.updated_at = datetime.now()
    return result
