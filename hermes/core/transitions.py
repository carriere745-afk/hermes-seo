"""Logique de transition conditionnelle entre agents.

Détermine si on passe à l'agent suivant, si on skip, ou si on bloque.
"""

from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import SessionConfig, SessionState


def should_skip_agent(
    agent_id: str,
    state: SessionState,
    active_agents: set[str],
    has_existing_content: bool = False,
    has_locale_target: bool = False,
) -> tuple[bool, str, str]:
    """Détermine si un agent doit être skippé.

    Returns (skip, reason, skip_type).
    skip_type = "auto" ou "user".
    """
    config = state.config

    # 1. Skip utilisateur
    if agent_id in config.user_skipped_agents:
        return True, f"Skip demandé par l'utilisateur", "user"

    # 2. Agent non inclus dans le mode qualité
    if agent_id not in active_agents:
        return True, f"Hors mode {config.mode.value}", "auto"

    # 3. Agents conditionnels
    if agent_id == "agent_08" and not has_existing_content:
        return True, "Aucun contenu existant en mémoire", "auto"

    if agent_id == "agent_20" and not has_locale_target:
        return True, "Aucune cible régionale/internationale", "auto"

    if agent_id == "agent_14":
        secteur = state.fiche_entreprise.get("secteur", "") if state.fiche_entreprise else ""
        from hermes.models.common import SECTEURS_REGLEMENTES
        if secteur not in SECTEURS_REGLEMENTES:
            return True, f"Secteur {secteur} non réglementé", "auto"

    # 4. Données manquantes (skip auto)
    if agent_id == "agent_03" and not (state.config.dry_run or _has_serp_api()):
        return True, "Aucune API SERP configurée", "auto"

    if agent_id == "agent_21":
        # Schema.org seulement si type de page le justifie
        from hermes.models.common import TypePage
        if state.type_page not in (
            TypePage.FICHE_PRODUIT.value,
            TypePage.FAQ.value,
            TypePage.SERVICE_LOCAL.value,
            TypePage.ARTICLE.value,
        ):
            return True, f"Type page {state.type_page} ne nécessite pas Schema.org", "auto"

    return False, "", ""


def get_skip_warning(agent_id: str) -> str:
    """Message d'avertissement quand un agent est skippé."""
    warnings = {
        "agent_02": "Le contenu sera moins ciblé sur le lecteur idéal.",
        "agent_03": "Pas d'analyse concurrentielle — le contenu pourrait manquer de pertinence SERP.",
        "agent_05": "Pas de stratégie de conversion — CTA et bénéfices non optimisés.",
        "agent_06": "Risque de contenu générique sans différenciation.",
        "agent_08": "Risque de cannibalisation entre pages du site.",
        "agent_12": "Le contenu sera moins visible dans les moteurs IA (ChatGPT, Perplexity…).",
        "agent_13": "Pas de vérification EEAT — impact potentiel sur le classement Google.",
        "agent_14": "Risque juridique : le contenu peut ne pas respecter les obligations légales.",
        "agent_16": "Maillage interne non optimisé — impact sur le SEO.",
        "agent_17": "Pas de suggestions de backlinks.",
        "agent_18": "Pas de déclinaison multiformat.",
        "agent_19": "Pas de test A/B — le titre/meta ne sera pas optimisé.",
        "agent_20": "Pas de localisation.",
        "agent_21": "Pas de rich snippets — visibilité réduite dans les SERP.",
        "agent_22": "Pas de plan visuel — les images sont à gérer manuellement.",
        "agent_23": "L'export CMS devra être fait manuellement.",
        "agent_24": "Pas de plan de mise à jour — le contenu peut devenir obsolète.",
        "agent_26": "Pas de feedback GSC — la boucle d'apprentissage est interrompue.",
    }
    return warnings.get(agent_id, "Étape non exécutée.")


def _has_serp_api() -> bool:
    """Vérifie si au moins une API SERP est configurée."""
    from hermes import config
    return bool(config.TALORDATA_API_KEY or config.SCRAPEDO_API_KEY or config.SERPSTACK_API_KEY)
