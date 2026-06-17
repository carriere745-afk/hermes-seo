"""Garde-fou du pipeline — arret intelligent sur echec critique.

Determine quels agents sont bloquants et quand le pipeline
doit s'arreter pour eviter les resultats "amateurs".
"""

from hermes.core.workflow import AGENT_ORDER
from hermes.models.common import AgentStatus

# Agents qui rendent le resultat inexploitable s'ils echouent.
# Ils sont TOUS non-skippables dans le registre.
CRITICAL_AGENTS: set[str] = {
    "agent_01",  # Brief Entreprise — fondation du pipeline
    "agent_03",  # Analyse SERP — pas d'analyse concurrentielle
    "agent_04",  # Intention — type de page inconnu
    "agent_07",  # Template — structure manquante
    "agent_09",  # Redaction — pas de contenu = pas de resultat
    "agent_15",  # Fact-checking — contenu non verifie
    "agent_25",  # Critique Qualite — pas de score
}

# Agents dont l'echec degrade fortement le resultat
# mais ne le bloque pas totalement.
SEVERE_DEGRADATION: set[str] = {
    "agent_02",  # Persona — contenu moins cible
    "agent_10",  # SEO — optimisation degradee
    "agent_11",  # AEO — pas d'optimisation IA
    "agent_12",  # GEO — pas d'optimisation Gemini/ChatGPT
    "agent_13",  # EEAT — score EEAT degrade
}


def get_failure_severity(agent_id: str) -> str:
    """Retourne la severite d'un echec.

    Returns:
        'critical' — resultat inexploitable, pipeline arrete
        'degraded' — resultat degrade mais continuable
        'acceptable' — impact mineur
    """
    if agent_id in CRITICAL_AGENTS:
        return "critical"
    if agent_id in SEVERE_DEGRADATION:
        return "degraded"
    return "acceptable"


def get_upstream_failures(
    agent_id: str, agent_results: dict
) -> list[str]:
    """Retourne les agents en amont qui ont echoue.

    Verifie si les agents precedents de la chaine ont echoue,
    ce qui pourrait compromettre l'agent courant.

    Args:
        agent_id: l'agent qu'on s'apprete a executer
        agent_results: dict {agent_id: AgentResult} de la session

    Returns:
        Liste des agents en echec en amont
    """
    try:
        idx = AGENT_ORDER.index(agent_id)
    except ValueError:
        return []

    failed_upstream = []
    for upstream_id in AGENT_ORDER[:idx]:
        result = agent_results.get(upstream_id)
        if result is None:
            continue
        status = result.status if hasattr(result, 'status') else None
        if status is None:
            continue
        status_val = status.value if hasattr(status, 'value') else str(status)
        if status_val in ("failed",):
            failed_upstream.append(upstream_id)

    return failed_upstream


def build_error_summary(session) -> dict:
    """Construit un resume de l'etat d'erreur du pipeline.

    Returns:
        {
            "critical_failed": [agent_ids],
            "degraded_failed": [agent_ids],
            "succeeded": [agent_ids],
            "not_run": [agent_ids],
            "can_resume": bool,
            "resume_from": agent_id or None,
        }
    """
    results = session.agent_results or {}

    succeeded = []
    critical_failed = []
    degraded_failed = []
    for aid in AGENT_ORDER:
        result = results.get(aid)
        if result is None:
            continue
        st = result.status if hasattr(result, 'status') else None
        if st is None:
            continue
        st_val = st.value if hasattr(st, 'value') else str(st)

        if st_val == "failed":
            if aid in CRITICAL_AGENTS:
                critical_failed.append(aid)
            else:
                degraded_failed.append(aid)
        elif st_val in ("completed", "skipped_auto", "skipped_user"):
            succeeded.append(aid)

    # Trouver jusqu'ou on a ete
    last_idx = -1
    for aid in succeeded:
        try:
            idx = AGENT_ORDER.index(aid)
            if idx > last_idx:
                last_idx = idx
        except ValueError:
            pass

    # Identifier les agents non executes
    not_run = [
        aid for aid in AGENT_ORDER
        if AGENT_ORDER.index(aid) > last_idx
        and aid not in critical_failed
        and aid not in degraded_failed
        and aid not in succeeded
    ]

    # Resume possible si au moins un agent a reussi
    resume_from = None
    if succeeded and last_idx >= 0 and last_idx + 1 < len(AGENT_ORDER):
        resume_from = AGENT_ORDER[last_idx + 1]

    return {
        "critical_failed": critical_failed,
        "degraded_failed": degraded_failed,
        "succeeded": succeeded,
        "not_run": not_run,
        "can_resume": resume_from is not None,
        "resume_from": resume_from,
        "last_successful": succeeded[-1] if succeeded else None,
    }
