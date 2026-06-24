"""Workflow Pipeline 6 — Maillage & Backlinks.

Orchestre les 18 agents B00-B17 via LangGraph StateGraph.
"""

import logging
from datetime import datetime

from langgraph.graph import StateGraph, END

from hermes.agents.backlinks import BACKLINKS_REGISTRY, BACKLINKS_ORDER
from hermes.models.backlinks import BacklinksState

logger = logging.getLogger("hermes.backlinks.workflow")


def build_backlinks_graph() -> StateGraph:
    graph = StateGraph(BacklinksState)

    for agent_id in BACKLINKS_ORDER:
        if agent_id in BACKLINKS_REGISTRY:
            graph.add_node(agent_id, BACKLINKS_REGISTRY[agent_id])

    if BACKLINKS_ORDER:
        graph.set_entry_point(BACKLINKS_ORDER[0])

    for i, agent_id in enumerate(BACKLINKS_ORDER):
        if i + 1 < len(BACKLINKS_ORDER):
            next_id = BACKLINKS_ORDER[i + 1]
            if next_id in BACKLINKS_REGISTRY:
                graph.add_edge(agent_id, next_id)
            else:
                graph.add_edge(agent_id, END)
        else:
            graph.add_edge(agent_id, END)

    return graph.compile()


async def run_backlinks_pipeline(state: BacklinksState) -> BacklinksState:
    if not state.startup_ok and not state.domain:
        state.status = "error"
        logger.error("Pipeline 6: domain requis")
        return state

    logger.info(f"Pipeline 6: mode={state.mode}, domain={state.domain}, "
                f"competitors={len(state.competitors)}")

    graph = build_backlinks_graph()
    config = {"configurable": {"thread_id": state.session_id}}

    try:
        final_state = await graph.ainvoke(state, config)
    except Exception as e:
        logger.error(f"Pipeline 6: workflow failed: {e}")
        state.status = "failed"
        state.errors.append(str(e))
        state.updated_at = datetime.now()
        return state

    if isinstance(final_state, dict):
        result = BacklinksState(**final_state)
    else:
        result = final_state

    result.updated_at = datetime.now()
    return result
