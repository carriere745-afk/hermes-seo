"""Agent 24 — Mise a jour / Fraicheur.

Planifie la revision periodique du contenu et surveille l'obsolescence
des sources. Frequence adaptee au secteur et au type de page.
Pas d'appel LLM — moteur de regles deterministe.
"""

from datetime import datetime, timedelta

from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import RefreshPlan
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# Frequences de revision par type de page (en jours)
FREQUENCE_PAR_TYPE: dict[str, int] = {
    "article": 180,      # 6 mois
    "pilier": 90,        # 3 mois
    "fiche_produit": 90,
    "faq": 120,
    "service_local": 90,
    "comparatif": 60,    # 2 mois — les prix changent
    "landing": 90,
    "news": 7,           # 1 semaine
    "glossaire": 365,    # 1 an
    "temoignage": 180,
}

# Frequence acceleree pour secteurs a evolution rapide
FREQUENCE_SECTEUR_ACCELERE: dict[str, int] = {
    "finance": 60,
    "sante": 90,
    "droit": 90,
    "cybersecurite": 30,  # Evolue tres vite
    "donnees_personnelles": 90,
}


def _compute_next_revision(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_24"
    agent_name = "Mise a jour"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"
    result.model_used = "rules-only"
    result.tokens_input = 0
    result.tokens_output = 0
    result.cost_estimated = 0.0

    try:
        type_page = state.type_page or "article"
        secteur = state.config.secteur or (state.fiche_entreprise or {}).get("secteur", "")
        fact = state.fact_check_data or {}
        geo = state.geo_data or {}
        serp = state.serp_data or {}

        # Determiner la frequence
        frequence = FREQUENCE_PAR_TYPE.get(type_page, 90)
        if secteur in FREQUENCE_SECTEUR_ACCELERE:
            frequence = min(frequence, FREQUENCE_SECTEUR_ACCELERE[secteur])

        next_date = _compute_next_revision(frequence)

        # Criteres d'obsolescence
        criteres: list[str] = []
        if type_page == "comparatif":
            criteres.append("Verifier que les prix et les offres sont a jour")
        if type_page == "news":
            criteres.append("Verifier que l'information n'est plus perimee — la dater ou la supprimer")
        if secteur in ("finance", "droit", "sante"):
            criteres.append(f"Verifier que les donnees reglementaires ({secteur}) sont a jour")
        if serp.get("keyword_difficulty", 0) > 0:
            criteres.append("Surveiller l'evolution du top 10 SERP — nouveaux concurrents ?")
        criteres.append("Verifier qu'aucun lien sortant n'est casse (HTTP 404)")
        criteres.append("Mettre a jour l'annee dans le titre si necessaire")

        # Sources a surveiller
        sources = list(geo.get("sources_primaires", [])) if isinstance(geo.get("sources_primaires"), list) else []
        sources_urls = [s.get("url", s) if isinstance(s, dict) else str(s) for s in sources[:5]]
        if not sources_urls:
            # Sources sectorielles par defaut
            if secteur == "finance":
                sources_urls = ["service-public.fr", "amf-France.org", "banque-france.fr"]
            elif secteur == "sante":
                sources_urls = ["ameli.fr", "has-sante.fr", "ansm.sante.fr"]
            elif secteur == "droit":
                sources_urls = ["legifrance.gouv.fr", "service-public.fr"]

        plan = RefreshPlan(
            date_prochaine_revision=next_date,
            frequence_jours=frequence,
            criteres_obsolescence=criteres,
            sources_a_surveiller=sources_urls,
        )

        state.plan_refresh = plan.model_dump()
        result.data = state.plan_refresh
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        plan = RefreshPlan(
            date_prochaine_revision=_compute_next_revision(90),
            frequence_jours=90,
            criteres_obsolescence=[f"Erreur lors de la planification: {e}"],
        )
        state.plan_refresh = plan.model_dump()
        result.data = state.plan_refresh
        result.status = AgentStatus.COMPLETED
        result.error_message = str(e)

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    log_agent_completed(agent_id, agent_name, result.duration_ms,
                        tokens_input=0, tokens_output=0,
                        cost_estimated=0.0, prompt_version="v1",
                        model_used="rules-only")
    state.last_completed_agent_id = agent_id
    return state
