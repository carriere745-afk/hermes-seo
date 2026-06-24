"""Workflow Pipeline 5 — Strategie Editoriale.

Orchestre les 18 agents ST00-ST11 via LangGraph StateGraph.
Pattern identique aux pipelines 2, 3 et 4.

Phases :
- Phase 0 : ST00 (startup)
- Phase 1 : ST01-ST05b (analyses)
- Phase 2 : ST06-ST10b (synthese)
- Phase 3 : ST11 (export)
"""

import logging
from datetime import datetime

from langgraph.graph import StateGraph, END

from hermes.agents.strategie import STRATEGIE_REGISTRY, STRATEGIE_ORDER
from hermes.models.strategie import StrategieState

logger = logging.getLogger("hermes.strategie.workflow")


def build_strategie_graph() -> StateGraph:
    graph = StateGraph(StrategieState)

    for agent_id in STRATEGIE_ORDER:
        if agent_id in STRATEGIE_REGISTRY:
            graph.add_node(agent_id, STRATEGIE_REGISTRY[agent_id])

    if STRATEGIE_ORDER:
        graph.set_entry_point(STRATEGIE_ORDER[0])

    for i, agent_id in enumerate(STRATEGIE_ORDER):
        if i + 1 < len(STRATEGIE_ORDER):
            next_id = STRATEGIE_ORDER[i + 1]
            if next_id in STRATEGIE_REGISTRY:
                graph.add_edge(agent_id, next_id)
            else:
                graph.add_edge(agent_id, END)
        else:
            graph.add_edge(agent_id, END)

    return graph.compile()


async def run_strategie_pipeline(state: StrategieState) -> StrategieState:
    if not state.startup_ok and not state.domain:
        state.status = "error"
        logger.error("Pipeline 5: domain requis")
        return state

    logger.info(f"Pipeline 5: mode={state.mode}, domain={state.domain}, "
                f"keywords={len(state.keywords_monitored)}, competitors={len(state.competitors)}")

    graph = build_strategie_graph()
    config = {"configurable": {"thread_id": state.session_id}}

    try:
        final_state = await graph.ainvoke(state, config)
    except Exception as e:
        logger.error(f"Pipeline 5: workflow failed: {e}")
        state.status = "failed"
        state.errors.append(str(e))
        state.updated_at = datetime.now()
        return state

    if isinstance(final_state, dict):
        result = StrategieState(**final_state)
    else:
        result = final_state

    result.updated_at = datetime.now()
    return result
