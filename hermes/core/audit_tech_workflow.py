"""Workflow LangGraph du Pipeline Audit Technique.

Orchestre les agents T00-T20 sequentiellement via StateGraph.
Pattern identique a audit_workflow.py (Pipeline 2).
"""

import logging
from datetime import datetime

from langgraph.graph import StateGraph, END

from hermes.agents.audit_tech import TECH_REGISTRY, TECH_ORDER
from hermes.models.audit_tech import TechAuditState

logger = logging.getLogger("hermes.audit_tech.workflow")


def build_tech_audit_graph() -> StateGraph:
    """Construit le graphe LangGraph du pipeline audit technique.

    Les agents sont enchaines sequentiellement dans TECH_ORDER.
    Chaque agent prend et retourne un TechAuditState.

    Returns: StateGraph compile
    """
    graph = StateGraph(TechAuditState)

    # Ajouter tous les agents implementes
    for agent_id in TECH_ORDER:
        if agent_id in TECH_REGISTRY:
            graph.add_node(agent_id, TECH_REGISTRY[agent_id])
        else:
            logger.warning(f"Agent {agent_id} dans TECH_ORDER mais pas dans TECH_REGISTRY — skip")

    # Premier agent = point d'entree
    if TECH_ORDER:
        graph.set_entry_point(TECH_ORDER[0])

    # Enchainement sequentiel
    for i, agent_id in enumerate(TECH_ORDER):
        if i + 1 < len(TECH_ORDER):
            next_id = TECH_ORDER[i + 1]
            if next_id in TECH_REGISTRY:
                graph.add_edge(agent_id, next_id)
            else:
                graph.add_edge(agent_id, END)
        else:
            graph.add_edge(agent_id, END)

    return graph.compile()


async def run_tech_audit(state: TechAuditState) -> TechAuditState:
    """Execute le pipeline d'audit technique complet.

    Args:
        state: TechAuditState initialise avec consentement, URLs, profil

    Returns: TechAuditState avec issues, scores, roadmap
    """
    if not state.consent_given:
        state.status = "awaiting_consent"
        logger.warning("Pipeline audit technique bloque : consentement requis")
        return state

    if not state.urls:
        state.status = "error"
        logger.error("Pipeline audit technique : aucune URL a auditer")
        return state

    logger.info(
        f"Pipeline Audit Technique: {len(state.urls)} URLs, "
        f"mode={state.mode}, profil={state.profile}, "
        f"CMS={state.cms_detected or 'a detecter'}"
    )

    try:
        graph = build_tech_audit_graph()
        config = {"configurable": {"thread_id": state.session_id}}
        final_state = await graph.ainvoke(state, config)

        # ainvoke retourne un dict, reconstruire le state
        if isinstance(final_state, dict):
            result = TechAuditState(**final_state)
        else:
            result = final_state

        result.status = "completed"
        result.updated_at = datetime.now()
        logger.info(f"Pipeline Audit Technique termine: {len(result.issues)} issues, score={result.scores.global_score}")
        return result

    except Exception as e:
        logger.error(f"Pipeline Audit Technique erreur: {e}")
        state.status = "error"
        state.error_count += 1
        return state
