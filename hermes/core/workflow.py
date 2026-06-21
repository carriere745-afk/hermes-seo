"""Construction du graphe LangGraph pour Hermes SEO.

Le graphe est construit dynamiquement à partir du registre des agents.
Chaque agent est un nœud, les transitions sont conditionnelles.
"""

from typing import Any, Optional

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from hermes.core.exceptions import SupervisorBlockError
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import AgentResult, SessionConfig, SessionState


# ─── Ordre canonique des agents ───────────────────────────────────────

AGENT_ORDER: list[str] = [
    "agent_00",
    "agent_01",
    "agent_02",
    "agent_03",
    "agent_04",
    "agent_05",
    "agent_06",
    "agent_07",
    "agent_08",
    "agent_09",
    "agent_10",
    "agent_11",
    "agent_12",
    "agent_13",
    "agent_14",
    "agent_15",
    "agent_16",
    "agent_17",
    "agent_18",
    "agent_19",
    "agent_20",
    "agent_21",
    "agent_22",
    "agent_23",
    "agent_24",
    "agent_25",
    "agent_26",
    "agent_27",
]


def _next_agent(current: str) -> Optional[str]:
    """Retourne l'agent suivant dans l'ordre canonique."""
    try:
        idx = AGENT_ORDER.index(current)
        if idx + 1 < len(AGENT_ORDER):
            return AGENT_ORDER[idx + 1]
        return None
    except ValueError:
        return None


def _prev_agent(current: str) -> Optional[str]:
    try:
        idx = AGENT_ORDER.index(current)
        if idx > 0:
            return AGENT_ORDER[idx - 1]
        return None
    except ValueError:
        return None


def build_supervisor_graph(
    agent_nodes: dict[str, callable],
    supervisor_func: callable,
    checkpointer: Any = None,
) -> StateGraph:
    """Construit le graphe LangGraph complet.

    Args:
        agent_nodes: dict {agent_id: node_function} pour chaque agent.
        supervisor_func: fonction de supervision appelée avant chaque transition.
        checkpointer: instance de checkpointer LangGraph (MemorySaver, SqliteSaver...).

    Returns:
        Un StateGraph compilé prêt à être invoqué.
    """
    if checkpointer is None:
        checkpointer = MemorySaver()

    graph = StateGraph(SessionState)

    # Ajouter tous les nœuds
    for agent_id, node_fn in agent_nodes.items():
        graph.add_node(agent_id, node_fn)

    # Ajouter le nœud superviseur (exécuté avant chaque agent)
    graph.add_node("__supervisor__", supervisor_func)

    # Point d'entrée : superviseur puis premier agent
    graph.set_entry_point("__supervisor__")

    # Transition du superviseur vers l'agent 00
    graph.add_edge("__supervisor__", "agent_00")

    # Chaîne principale : chaque agent → superviseur → suivant
    for i, agent_id in enumerate(AGENT_ORDER):
        next_id = _next_agent(agent_id)
        if next_id:
            # Chaque agent va au superviseur, qui décide
            graph.add_edge(agent_id, "__supervisor__")

            # Le superviseur décide du prochain agent
            def make_router(next_agent: str):
                def router(state: SessionState) -> str:
                    result = state.agent_results.get(
                        state.current_agent_id or "",
                        AgentResult(agent_id="", status=AgentStatus.PENDING),
                    )

                    # Si l'agent courant a réussi ou a été skippé, on continue
                    if result.status in (
                        AgentStatus.COMPLETED,
                        AgentStatus.SKIPPED_AUTO,
                        AgentStatus.SKIPPED_USER,
                    ):
                        return next_agent

                    # Si échec, on arrête
                    if result.status == AgentStatus.FAILED:
                        return END

                    # Sinon on bloque
                    return END

                return router

            graph.add_conditional_edges(
                "__supervisor__",
                make_router(next_id),
                {
                    next_id: next_id,
                    END: END,
                },
            )
        else:
            # Dernier agent → fin
            graph.add_edge(agent_id, END)

    return graph.compile(checkpointer=checkpointer)


# ─── Helpers pour le séquencement ──────────────────────────────────────


def get_agents_for_mode(mode: QualityMode) -> set[str]:
    """Retourne les agents activés pour un mode qualité donné."""
    fast = {
        "agent_00", "agent_01", "agent_04", "agent_07",
        "agent_09", "agent_10", "agent_11", "agent_15", "agent_25",
    }
    standard = fast | {
        "agent_02", "agent_03", "agent_05", "agent_06", "agent_08",
        "agent_12", "agent_13", "agent_16", "agent_21", "agent_22", "agent_23",
    }
    premium = standard | {
        "agent_14", "agent_17", "agent_18", "agent_19",
        "agent_20", "agent_24", "agent_26", "agent_27",
    }
    compliance = premium  # Mêmes agents, comportement renforcé
    debug = set(AGENT_ORDER)

    mapping = {
        QualityMode.FAST: fast,
        QualityMode.STANDARD: standard,
        QualityMode.PREMIUM: premium,
        QualityMode.COMPLIANCE: compliance,
        QualityMode.DEBUG: debug,
    }
    return mapping.get(mode, standard)


def get_active_agents(
    mode: QualityMode,
    secteur: Optional[str] = None,
    user_skipped: Optional[list[str]] = None,
    has_existing_content: bool = False,
    has_locale_target: bool = False,
) -> list[str]:
    """Calcule la liste des agents actifs selon le mode et le contexte.

    Combine le mode qualité, les déclencheurs conditionnels, et les skips
    utilisateur pour déterminer quels agents exécuter.
    """
    active = get_agents_for_mode(mode)
    skipped = set(user_skipped or [])

    # Agents toujours obligatoires (même en fast)
    mandatory = {"agent_00", "agent_01", "agent_04", "agent_07", "agent_09",
                 "agent_10", "agent_11", "agent_15", "agent_25"}

    # Agents conditionnels
    from hermes.models.common import SECTEURS_REGLEMENTES

    if secteur and secteur in SECTEURS_REGLEMENTES:
        active.add("agent_14")

    # Agent 08 obligatoire si contenus existants
    if has_existing_content:
        active.add("agent_08")

    # Agent 20 obligatoire si cible multilingue
    if has_locale_target:
        active.add("agent_20")

    # Forcer les obligatoires dans tous les cas
    active |= mandatory

    # Appliquer les skips utilisateur (sauf pour les non-skippables)
    non_skippable = {
        "agent_00", "agent_01", "agent_04", "agent_07",
        "agent_15", "agent_25",
    }
    if mode != QualityMode.DEBUG:
        # En mode non-debug, on ne peut pas skipper les non-skippables
        skipped -= non_skippable

    active -= skipped

    # Ordonner selon AGENT_ORDER
    return [a for a in AGENT_ORDER if a in active]
