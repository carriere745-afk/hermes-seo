"""Workflow du Pipeline Audit de Contenu.

Orchestre les 10 agents sequentiellement via LangGraph.
"""

import asyncio
import logging
from datetime import datetime

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from hermes.agents.audit import AUDIT_REGISTRY, AUDIT_ORDER
from hermes.models.audit import AuditSessionState

logger = logging.getLogger("hermes.audit.workflow")


def build_audit_graph(checkpointer=None) -> StateGraph:
    """Construit le graphe LangGraph pour le pipeline Audit de Contenu."""
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph = StateGraph(AuditSessionState)

    # Ajouter tous les agents comme noeuds
    for agent_id in AUDIT_ORDER:
        if agent_id in AUDIT_REGISTRY:
            graph.add_node(agent_id, AUDIT_REGISTRY[agent_id])

    # Point d'entree
    graph.set_entry_point("ac00")

    # Enchainement sequentiel
    for i, agent_id in enumerate(AUDIT_ORDER):
        next_id = AUDIT_ORDER[i + 1] if i + 1 < len(AUDIT_ORDER) else END
        graph.add_edge(agent_id, next_id)

    return graph.compile(checkpointer=checkpointer)


async def run_audit_pipeline(
    urls: list[str],
    site_url: str = "",
    mode: str = "standard",
) -> AuditSessionState:
    """Execute le pipeline complet d'audit de contenu.

    Args:
        urls: liste d'URLs a auditer
        site_url: URL racine du site (pour le rapport)
        mode: mode qualite (fast/standard/premium/debug)

    Returns: AuditSessionState avec scores, briefs et roadmap
    """
    session = AuditSessionState(
        session_id=datetime.now().strftime("audit_%Y%m%d_%H%M%S"),
        site_url=site_url or urls[0] if urls else "",
        urls=urls,
        mode=mode,
        status="created",
    )

    graph = build_audit_graph()
    config = {"configurable": {"thread_id": session.session_id}}

    logger.info(f"Audit pipeline starting: {len(urls)} URLs, mode={mode}")
    result_dict = await graph.ainvoke(session, config)
    # LangGraph retourne un dict, reconstruire le modele
    result = AuditSessionState.model_validate(result_dict)
    logger.info(f"Audit pipeline completed: {result.status}")

    return result
