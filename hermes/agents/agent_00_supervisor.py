"""Agent 00 — Superviseur central.

Verifie l'integrite du pipeline avant chaque transition.
Pure logique Python, pas d'appel LLM.

Responsabilites :
1. Verifier que l'agent precedent a termine correctement
2. Valider sa sortie contre le modele Pydantic attendu
3. Verifier la presence des donnees requises par l'agent suivant
4. Controler la coherence inter-champs
5. Bloquer la progression si anomalie detectee
"""

from typing import Any, Optional

from hermes.core.transitions import should_skip_agent
from hermes.models.agent_data import (
    AeoBlocks,
    AntiCannibData,
    Brouillon,
    ConformiteData,
    DifferenciationData,
    EeatScore,
    ExportData,
    ExternalLinks,
    FactCheckData,
    FeedbackData,
    FicheEntreprise,
    FichePersona,
    GeoData,
    ImagePlan,
    IntentTypeData,
    InternalLinks,
    LocalisedData,
    MultiformatData,
    OffreConversion,
    RefreshPlan,
    SchemaData,
    ScoresFinaux,
    SeoData,
    SerpData,
    SupervisorVerdict,
    TemplateData,
    VariantsAB,
)
from hermes.models.common import AgentStatus, QualityMode, SessionStatus
from hermes.models.session import AgentResult, SessionState

# ─── Mapping agent_id → (donnee_produite, modele_pydantic, champs_obligatoires) ───

AGENT_OUTPUT_SPEC: dict[str, tuple[str, type, list[str]]] = {
    "agent_01": ("fiche_entreprise", FicheEntreprise, ["nom", "secteur", "positionnement"]),
    "agent_02": ("fiche_persona", FichePersona, ["nom_persona", "maturite"]),
    "agent_03": ("serp_data", SerpData, ["top10"]),
    "agent_04": ("intention_type_data", IntentTypeData, ["intention", "type_page"]),
    "agent_05": ("offre_conversion_data", OffreConversion, ["cta_principal"]),
    "agent_06": ("angles_differenciants", DifferenciationData, ["angle_principal"]),
    "agent_07": ("template_data", TemplateData, ["template_id", "structure"]),
    "agent_08": ("anti_cannib_data", AntiCannibData, ["action"]),
    "agent_09": ("brouillon_html", Brouillon, ["html"]),
    "agent_10": ("seo_data", SeoData, ["title_optimise"]),
    "agent_11": ("aeo_blocks", AeoBlocks, ["en_bref"]),
    "agent_12": ("geo_data", GeoData, ["entites_nommees"]),
    "agent_13": ("score_eeat", EeatScore, ["score_global"]),
    "agent_14": ("conformite_data", ConformiteData, ["valide", "risque_juridique"]),
    "agent_15": ("fact_check_data", FactCheckData, ["score_fiabilite"]),
    "agent_16": ("internal_links", InternalLinks, ["liens_proposes"]),
    "agent_17": ("external_links", ExternalLinks, ["liens_sortants"]),
    "agent_18": ("multiformat_data", MultiformatData, ["session_parent"]),
    "agent_19": ("variants_ab", VariantsAB, ["variants"]),
    "agent_20": ("localised_data", LocalisedData, ["versions"]),
    "agent_21": ("ld_json", SchemaData, ["ld_json"]),
    "agent_22": ("image_plan", ImagePlan, ["images"]),
    "agent_23": ("export_data", ExportData, ["format", "contenu_formate"]),
    "agent_24": ("plan_refresh", RefreshPlan, ["date_prochaine_revision"]),
    "agent_25": ("scores", ScoresFinaux, ["score_total", "seuil_atteint"]),
    "agent_26": ("feedback_data", FeedbackData, ["data_gsc"]),
}

# ─── Dépendances : ce dont chaque agent a besoin produit par les agents précédents ───

AGENT_DEPENDENCIES: dict[str, list[str]] = {
    "agent_00": [],
    "agent_01": [],
    "agent_02": ["agent_01"],                                  # besoin fiche_entreprise
    "agent_03": [],
    "agent_04": ["agent_03"],                                  # besoin serp_data
    "agent_05": ["agent_01", "agent_02", "agent_04"],          # besoin entreprise, persona, intention
    "agent_06": ["agent_03", "agent_05"],                      # besoin serp, offre
    "agent_07": ["agent_04"],                                  # besoin intention, type_page
    "agent_08": ["agent_03", "agent_06"],                      # besoin serp, angles
    "agent_09": ["agent_01", "agent_02", "agent_03", "agent_04",
                 "agent_05", "agent_06", "agent_07", "agent_08"],  # a besoin de tout
    "agent_10": ["agent_09"],                                  # besoin brouillon
    "agent_11": ["agent_09"],                                  # besoin brouillon
    "agent_12": ["agent_09", "agent_03"],                      # besoin brouillon, serp
    "agent_13": ["agent_09", "agent_01"],                      # besoin brouillon, entreprise
    "agent_14": ["agent_09", "agent_01"],                      # besoin brouillon, entreprise
    "agent_15": ["agent_09", "agent_03"],                      # besoin brouillon, serp
    "agent_16": ["agent_09"],                                  # besoin brouillon
    "agent_17": ["agent_09", "agent_03"],                      # besoin brouillon, serp
    "agent_18": ["agent_09"],                                  # besoin brouillon
    "agent_19": ["agent_10"],                                  # besoin seo_data
    "agent_20": ["agent_09"],                                  # besoin brouillon
    "agent_21": ["agent_04", "agent_09"],                      # besoin type_page, contenu
    "agent_22": ["agent_09"],                                  # besoin brouillon
    "agent_23": ["agent_09", "agent_10", "agent_11", "agent_21"],  # besoin contenu final
    "agent_24": ["agent_09", "agent_15"],                      # besoin brouillon, fact-check
    "agent_25": ["agent_09", "agent_10", "agent_11", "agent_12",
                 "agent_13", "agent_14", "agent_15"],           # besoin contenu + optimisations
    "agent_26": [],                                            # independant, post-publication
}


# ─── Mapping field_name → SessionState attribute ───

def _get_session_field(session: SessionState, field_name: str) -> Optional[Any]:
    """Retourne la valeur d'un champ de session par son nom."""
    # Certains champs ont des noms composes
    field_map = {
        "fiche_entreprise": session.fiche_entreprise,
        "fiche_persona": session.fiche_persona,
        "serp_data": session.serp_data,
        "intention": session.intention,
        "type_page": session.type_page,
        "offre_conversion_data": session.offre_conversion_data,
        "angles_differenciants": session.angles_differenciants,
        "template_data": session.template_data,
        "anti_cannib_data": session.anti_cannib_data,
        "brouillon_html": session.brouillon_html,
        "seo_data": session.seo_data,
        "aeo_blocks": session.aeo_blocks,
        "geo_data": session.geo_data,
        "score_eeat": session.score_eeat,
        "conformite_data": session.conformite_data,
        "fact_check_data": session.fact_check_data,
        "internal_links": session.internal_links,
        "external_links": session.external_links,
        "multiformat_data": session.multiformat_data,
        "variants_ab": session.variants_ab,
        "localised_data": session.localised_data,
        "ld_json": session.ld_json,
        "image_plan": session.image_plan,
        "export_data": session.export_data,
        "plan_refresh": session.plan_refresh,
        "scores": session.scores,
        "feedback_data": session.feedback_data,
        # Champs composes
        "intention_type_data": {
            "intention": session.intention,
            "type_page": session.type_page,
        },
    }
    return field_map.get(field_name)


_AGENT_ORDER_INDEX: dict[str, int] = {}


def _get_agent_index(agent_id: str) -> int:
    """Index de l'agent dans l'ordre canonique."""
    if not _AGENT_ORDER_INDEX:
        from hermes.core.workflow import AGENT_ORDER
        for i, aid in enumerate(AGENT_ORDER):
            _AGENT_ORDER_INDEX[aid] = i
    return _AGENT_ORDER_INDEX.get(agent_id, 999)


def _get_previous_agent_id(state: SessionState) -> Optional[str]:
    """Identifie l'agent qui vient de s'executer."""
    current = state.current_agent_id
    if current is None:
        return None

    from hermes.core.workflow import AGENT_ORDER
    current_idx = _get_agent_index(current)

    # L'agent precedent est le dernier complete avant current
    best_idx = -1
    best_id = None
    for agent_id, result in state.agent_results.items():
        agent_idx = _get_agent_index(agent_id)
        if agent_idx < current_idx and result.status == AgentStatus.COMPLETED:
            if agent_idx > best_idx:
                best_idx = agent_idx
                best_id = agent_id
    return best_id


async def run(state: SessionState) -> SessionState:
    """Superviseur central — execute avant chaque transition.

    Verifie l'etat du pipeline et produit un verdict.
    Le verdict est stocke dans la session pour la prise de decision.
    """
    agent_id = "agent_00"

    # Initialiser le resultat si absent
    if agent_id not in state.agent_results:
        state.agent_results[agent_id] = AgentResult(
            agent_id=agent_id, agent_name="Superviseur central",
        )
    result = state.agent_results[agent_id]
    result.status = AgentStatus.RUNNING

    current_agent_id = state.current_agent_id
    verdict = _evaluate(state)
    state.warnings.extend(verdict.warnings)

    if not verdict.valid:
        state.status = SessionStatus.BLOCKED
        state.warnings.append(
            f"[Superviseur] Pipeline bloque a {current_agent_id}: "
            f"{'; '.join(verdict.blocked_reasons)}"
        )
        result.status = AgentStatus.COMPLETED  # Le superviseur a fait son job
    else:
        result.status = AgentStatus.COMPLETED

    return state


def _evaluate(state: SessionState) -> SupervisorVerdict:
    """Evalue l'etat actuel du pipeline et produit un verdict.

    Cette fonction est appelee avant chaque transition.
    Elle verifie :
    1. Presence et validite du keyword
    2. Etat de la session
    3. Resultat de l'agent precedent
    4. Validation Pydantic de la sortie
    5. Dependances pour l'agent suivant
    6. Coherence inter-champs
    """
    reasons: list[str] = []
    warnings: list[str] = []

    current = state.current_agent_id

    # ── 0. Verifications fondamentales ──

    if not state.keyword:
        reasons.append("Keyword manquant dans la session")
        return SupervisorVerdict(
            valid=False, blocked_reasons=reasons, warnings=warnings,
            next_agent_id="", next_action="block",
        )

    if state.status == SessionStatus.FAILED:
        reasons.append("Session en etat failed")
        return SupervisorVerdict(
            valid=False, blocked_reasons=reasons, warnings=warnings,
            next_agent_id="", next_action="block",
        )

    # ── 1. Verifier le resultat de l'agent precedent ──

    prev_agent = _get_previous_agent_id(state)

    if prev_agent and prev_agent in state.agent_results:
        result = state.agent_results[prev_agent]

        if result.status == AgentStatus.FAILED:
            reasons.append(
                f"Agent {prev_agent} a echoue: {result.error_message or 'erreur inconnue'}"
            )
            return SupervisorVerdict(
                valid=False, blocked_reasons=reasons, warnings=warnings,
                next_agent_id="", next_action="block",
            )

        # Valider la sortie Pydantic si l'agent a termine
        if result.status == AgentStatus.COMPLETED and prev_agent in AGENT_OUTPUT_SPEC:
            field_name, model_class, _ = AGENT_OUTPUT_SPEC[prev_agent]

            if field_name == "intention_type_data":
                # Cas special : deux champs separes
                data_for_validation = {
                    "intention": state.intention,
                    "type_page": state.type_page,
                }
            else:
                data_for_validation = _get_session_field(state, field_name)

            if data_for_validation is not None:
                valid, error_msg = _validate_output(
                    model_class, data_for_validation, prev_agent
                )
                if not valid:
                    reasons.append(error_msg)
                else:
                    # Stocker intention et type_page dans les champs dedies
                    if prev_agent == "agent_04" and isinstance(data_for_validation, dict):
                        if not state.intention:
                            state.intention = data_for_validation.get("intention")
                        if not state.type_page:
                            state.type_page = data_for_validation.get("type_page")
            else:
                # Donnees manquantes pour un agent complete → anomalie
                warnings.append(
                    f"Agent {prev_agent} a termine mais {field_name} est absent. "
                    f"L'agent n'a pas correctement ecrit sa sortie."
                )

    # ── 2. Si current est agent_00 (debut), on laisse passer ──
    if current == "agent_00":
        return SupervisorVerdict(
            valid=True, blocked_reasons=[], warnings=warnings,
            next_agent_id="agent_01", next_action="proceed",
        )

    # ── 3. Verifier les dependances pour current ──
    if current and current in AGENT_DEPENDENCIES:
        deps = AGENT_DEPENDENCIES[current]

        for dep_id in deps:
            dep_spec = AGENT_OUTPUT_SPEC.get(dep_id)
            if dep_spec is None:
                continue

            field_name, _, _ = dep_spec
            if field_name == "intention_type_data":
                dep_data = {
                    "intention": state.intention,
                    "type_page": state.type_page,
                }
            else:
                dep_data = _get_session_field(state, field_name)

            if dep_data is None:
                # Si le dependance est un agent skippe, c'est normal
                dep_result = state.agent_results.get(dep_id)
                if dep_result and dep_result.status in (
                    AgentStatus.SKIPPED_AUTO,
                    AgentStatus.SKIPPED_USER,
                ):
                    skipped_deps = state.config.user_skipped_agents
                    if dep_id not in skipped_deps:
                        warnings.append(
                            f"Agent {dep_id} a ete ignore ({dep_result.status.value}). "
                            f"L'agent {current} pourrait produire un resultat degrade."
                        )
                    continue

                reasons.append(
                    f"Donnee manquante pour {current}: {field_name} "
                    f"(depend de {dep_id}, statut: {dep_result.status.value if dep_result else 'absent'})"
                )

    # ── 4. Coherence inter-champs ──

    _check_consistency(state, warnings)

    # ── 5. Verdict final ──

    if reasons:
        return SupervisorVerdict(
            valid=False, blocked_reasons=reasons, warnings=warnings,
            next_agent_id="", next_action="block",
        )

    # Determiner le prochain agent
    next_id = _get_next_agent(current, state)

    return SupervisorVerdict(
        valid=True, blocked_reasons=[], warnings=warnings,
        next_agent_id=next_id or "", next_action="proceed",
    )


def _get_next_agent(current: Optional[str], state: SessionState) -> Optional[str]:
    """Determine l'agent suivant dans la sequence."""
    from hermes.core.workflow import AGENT_ORDER

    if current is None:
        return "agent_00"

    try:
        idx = AGENT_ORDER.index(current)
        if idx + 1 < len(AGENT_ORDER):
            return AGENT_ORDER[idx + 1]
        return None
    except ValueError:
        return None


def _validate_output(
    model_class: type, data: Any, agent_id: str
) -> tuple[bool, str]:
    """Valide la sortie d'un agent contre son modele Pydantic.

    Returns (ok, error_message).
    """
    try:
        if data is None:
            return False, f"[{agent_id}] Sortie absente (None)"

        if isinstance(data, dict):
            model_class.model_validate(data)
        elif hasattr(data, "model_dump"):
            pass  # Deja un modele Pydantic, valide par construction
        else:
            return False, f"[{agent_id}] Type de sortie inattendu: {type(data).__name__}"

        return True, ""
    except Exception as e:
        return False, f"[{agent_id}] Validation echouee: {e}"


def _check_consistency(state: SessionState, warnings: list[str]) -> None:
    """Verifie la coherence entre les champs de la session."""

    # Intention vs type de page
    if state.intention and state.type_page:
        incoherences = {
            ("transactionnelle", "news"): "Intention transactionnelle mais type news",
            ("informative", "fiche_produit"): "Intention informative mais fiche produit",
            ("locale", "glossaire"): "Intention locale mais glossaire",
            ("comparative", "landing"): "Intention comparative mais landing",
        }
        key = (state.intention, state.type_page)
        if key in incoherences:
            warnings.append(f"Incoherence: {incoherences[key]}")

    # Secteur reglemente sans agent 14
    if state.config.secteur:
        from hermes.models.common import SECTEURS_REGLEMENTES
        if state.config.secteur in SECTEURS_REGLEMENTES:
            result_14 = state.agent_results.get("agent_14")
            if result_14 and result_14.status in (
                AgentStatus.SKIPPED_AUTO,
                AgentStatus.SKIPPED_USER,
            ):
                warnings.append(
                    f"Secteur reglemente ({state.config.secteur}) "
                    f"mais Agent 14 (Conformite) est ignore. Risque juridique eleve."
                )

    # Brouillon present mais pas de SEO
    if state.brouillon_html:
        result_10 = state.agent_results.get("agent_10")
        if result_10 and result_10.status == AgentStatus.FAILED:
            warnings.append("Brouillon redige mais optimisation SEO a echoue.")

    # Fact-checking : erreurs majeures
    if state.fact_check_data and isinstance(state.fact_check_data, dict):
        erreurs = state.fact_check_data.get("erreurs", [])
        critiques = [e for e in erreurs if isinstance(e, dict) and e.get("gravite") == "critique"]
        if critiques:
            warnings.append(
                f"{len(critiques)} erreur(s) factuelle(s) critique(s) detectee(s). "
                f"Le contenu ne devrait pas etre publie sans correction."
            )

    # Scores finaux
    if state.scores and isinstance(state.scores, dict):
        seuil = state.scores.get("seuil_atteint")
        if seuil is False:
            score_total = state.scores.get("score_total", 0)
            warnings.append(
                f"Score qualite {score_total}/100 inferieur au seuil de publication. "
                f"Corrections recommandees avant publication."
            )
