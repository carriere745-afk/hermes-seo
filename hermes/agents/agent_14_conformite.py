"""Agent 14 — Conformite sectorielle.

Applique les regles specifiques au secteur (finance, sante, droit,
enfants, cybersecurite, etc.). Conditionnellement obligatoire pour
les secteurs reglementes.

Double couche : moteur de regles deterministe + verification LLM optionnelle.
"""

from datetime import datetime
from html.parser import HTMLParser

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import ConformiteData
from hermes.models.common import AgentStatus, SECTEURS_REGLEMENTES
from hermes.models.session import AgentResult, SessionState


# ─── Regles de conformite par secteur ──────────────────────────────────

SECTOR_RULES: dict[str, dict] = {
    "finance": {
        "mentions_obligatoires": [
            "Les performances passees ne prejudent pas des performances futures",
            "Ce produit presente un risque de perte en capital",
            "Document non contractuel a valeur indicative",
        ],
        "avertissements_selon_type": {
            "produit": "Ceci n'est pas un conseil en investissement personnalise.",
            "comparatif": " Ce comparatif est fourni a titre indicatif et ne constitue pas un conseil.",
            "article": "Cet article ne constitue pas un conseil financier personnalise.",
        },
        "contenus_interdits": [
            "conseil en investissement personnalise",
            "promesse de rendement garanti",
            "rendement garanti",
            "garantie de performance",
            "garanti sans risque",
        ],
        "obligations": [
            "Mentionner la date de mise a jour des donnees financieres",
            "Identifier clairement le statut de l'emetteur (courtier, CIF, banque...)",
            "Inclure un avertissement fiscal si applicable",
        ],
        "risque_base": "modere",
    },
    "sante": {
        "mentions_obligatoires": [
            "Cet article ne remplace pas une consultation medicale",
            "En cas d'urgence, contactez le 15 (SAMU) ou le 112",
            "Les informations fournies le sont a titre educatif uniquement",
        ],
        "contenus_interdits": [
            "diagnostic medical",
            "promesse de guerison",
            "guerison garantie",
            "methode garantit la guerison",
            "recommandation de traitement sans avis medical",
            "traitement miraculeux",
        ],
        "obligations": [
            "Citer des sources medicales officielles (HAS, ANSM, Vidal, ameli.fr)",
            "Preciser la date de redaction (information medicale perimee = danger)",
            "Ne pas citer de marques de medicaments sans precaution",
            "Eviter les termes 'toujours', 'jamais', 'garanti' pour les resultats",
        ],
        "risque_base": "eleve",
    },
    "droit": {
        "mentions_obligatoires": [
            "Cet article ne constitue pas un conseil juridique",
            "Pour une situation personnelle, consultez un avocat",
            "Les informations sont fournies a titre informatif uniquement",
        ],
        "contenus_interdits": [
            "conseil juridique personnalise",
            "interpretation de la loi sans reference au texte officiel",
        ],
        "obligations": [
            "Citer les textes de loi applicables (article, loi, date)",
            "Preciser la juridiction concernee (droit francais, europeen...)",
            "Mentionner la date de derniere mise a jour de l'article de loi cite",
        ],
        "risque_base": "eleve",
    },
    "enfants": {
        "mentions_obligatoires": [
            "Ce contenu est destine aux adultes responsables d'enfants",
            "Un enfant doit toujours etre supervise par un adulte",
        ],
        "contenus_interdits": [
            "collecte de donnees personnelles de mineurs",
            "incitation a l'achat direct par des enfants",
            "contenu inapproprie pour les mineurs",
        ],
        "obligations": [
            "Verifier que le contenu est adapte a l'age du public cible",
            "Ne pas inclure de liens vers des contenus non filtres",
            "Mentionner les controles parentaux si applicable",
        ],
        "risque_base": "eleve",
    },
    "cybersecurite": {
        "mentions_obligatoires": [
            "Ce contenu est fourni a titre educatif",
            "Les techniques decrites peuvent etre illegales si utilisees sans autorisation",
        ],
        "contenus_interdits": [
            "tutoriel de piratage",
            "methode de contournement de securite sans contexte ethique",
            "divulgation de vulnerabilite sans correctif",
        ],
        "obligations": [
            "Preciser le cadre legal (test d'intrusion autorise, bug bounty...)",
            "Mentionner l'ANSSI ou le CERT-FR quand pertinent",
            "Rappeler les sanctions penales applicables",
        ],
        "risque_base": "critique",
    },
    "donnees_personnelles": {
        "mentions_obligatoires": [
            "Conformement au RGPD, vous disposez d'un droit d'acces et de rectification",
            "Les exemples utilisent des donnees fictives",
        ],
        "contenus_interdits": [
            "publication de donnees personnelles reelles sans consentement",
            "conseil de collecte de donnees sans base legale",
        ],
        "obligations": [
            "Citer le RGPD et la CNIL",
            "Rappeler les principes de minimisation et de finalite",
            "Ne pas utiliser d'exemples avec de vraies donnees personnelles",
        ],
        "risque_base": "eleve",
    },
    "vehicules": {
        "mentions_obligatoires": [
            "Les donnees de consommation sont fournies a titre indicatif (cycle WLTP)",
            "Respectez le Code de la Route en toutes circonstances",
        ],
        "contenus_interdits": [
            "incitation a la vitesse excessive",
            "modification illegale de vehicule",
        ],
        "risque_base": "modere",
    },
    "produits_reglementes": {
        "mentions_obligatoires": [
            "Ce produit est soumis a reglementation. Verifiez sa conformite.",
            "Les certifications mentionnees sont valables a la date de publication.",
        ],
        "obligations": [
            "Mentionner les certifications et normes applicables (CE, NF, ISO...)",
            "Indiquer les restrictions d'usage ou contre-indications",
            "Preciser la tranche d'age recommandee si applicable",
        ],
        "risque_base": "modere",
    },
    "rh": {
        "mentions_obligatoires": [
            "Les informations fournies ne constituent pas un conseil RH personnalise",
            "Conformement au Code du Travail, les regles peuvent varier selon la convention collective",
        ],
        "contenus_interdits": [
            "conseil juridique en droit du travail sans reference au Code du Travail",
            "discrimination basee sur des criteres proteges",
        ],
        "obligations": [
            "Citer les articles du Code du Travail applicables",
            "Preciser que les conventions collectives peuvent deroger",
            "Mentionner la date de mise a jour (droit du travail evolue rapidement)",
        ],
        "risque_base": "eleve",
    },
}


def _strip_html(html: str, limit: int = 5000) -> str:
    class _S(HTMLParser):
        def __init__(self):
            super().__init__()
            self.t: list[str] = []
        def handle_data(self, d):
            self.t.append(d)
    s = _S(); s.feed(html[:limit])
    return " ".join(s.t)


def _check_rules(texte: str, secteur: str, type_page: str = "article") -> ConformiteData:
    """Applique le moteur de regles deterministe."""
    rules = SECTOR_RULES.get(secteur)
    if rules is None:
        return ConformiteData(valide=True, risque_juridique="faible",
                              regles_appliquees=[f"Aucune regle specifique pour le secteur '{secteur}'"])

    texte_lower = texte.lower()
    avertissements: list[str] = []
    mentions_manquantes: list[str] = []
    contenus_detectes: list[str] = []
    regles_appliquees: list[str] = [f"Regles conformite appliquees pour le secteur '{secteur}'"]

    # Verifier les mentions obligatoires
    for mention in rules.get("mentions_obligatoires", []):
        if mention.lower() not in texte_lower:
            mentions_manquantes.append(mention)

    # Verifier les avertissements adaptes au type de page
    avertissements_par_type = rules.get("avertissements_selon_type", {})
    if type_page in avertissements_par_type:
        avert = avertissements_par_type[type_page]
        if avert.lower() not in texte_lower:
            avertissements.append(avert)

    # Verifier les contenus interdits
    import re as _re
    for interdit in rules.get("contenus_interdits", []):
        mots = interdit.lower().split()
        mots_significatifs = [m for m in mots if len(m) > 3]

        if len(mots_significatifs) >= 2:
            # Word-boundary matching (evite "recommandation" dans "recommandations",
            # "medical" dans "medicale")
            found = 0
            for m in mots_significatifs:
                if _re.search(r'\b' + _re.escape(m) + r'\b', texte_lower):
                    found += 1
            if found >= 2:
                negated = False
                for m in mots_significatifs:
                    match = _re.search(r'\b' + _re.escape(m) + r'\b', texte_lower)
                    if match:
                        idx = match.start()
                        contexte = texte_lower[max(0, idx - 40):idx]
                        if any(neg in contexte for neg in (
                            "ne constitue pas", "n'est pas", "ne represente pas",
                            "ne doit pas", "ne constitue en aucun cas",
                            "ne saurait constituer",
                        )):
                            negated = True
                            break
                if not negated:
                    contenus_detectes.append(interdit)
        elif len(mots_significatifs) == 1:
            if _re.search(r'\b' + _re.escape(mots_significatifs[0]) + r'\b', texte_lower):
                contenus_detectes.append(interdit)
        else:
            if interdit.lower() in texte_lower:
                contenus_detectes.append(interdit)

    # Verifier les obligations
    obligations_remplies = 0
    for obligation in rules.get("obligations", []):
        # Verification partielle (presence de mots-cles de l'obligation)
        mots_cles = [w for w in obligation.lower().split() if len(w) > 5]
        if mots_cles and any(mot in texte_lower for mot in mots_cles):
            obligations_remplies += 1

    total_obligations = len(rules.get("obligations", []))
    obligations_non_remplies = max(0, total_obligations - obligations_remplies)

    # Determiner le risque
    risque = rules.get("risque_base", "faible")
    if contenus_detectes:
        risque = "critique"

    valide = len(contenus_detectes) == 0 and len(mentions_manquantes) <= 2

    if mentions_manquantes:
        regles_appliquees.append(
            f"{len(mentions_manquantes)} mention(s) obligatoire(s) manquante(s)"
        )
    if contenus_detectes:
        regles_appliquees.append(
            f"{len(contenus_detectes)} contenu(s) interdit(s) detecte(s)"
        )
    if obligations_non_remplies > 0:
        regles_appliquees.append(
            f"{obligations_non_remplies}/{total_obligations} obligation(s) non remplie(s)"
        )

    return ConformiteData(
        valide=valide,
        avertissements_requis=avertissements,
        mentions_obligatoires=mentions_manquantes,
        regles_appliquees=regles_appliquees,
        risque_juridique=risque,
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_14"
    agent_name = "Conformite sectorielle"
    start_time = datetime.now()
    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"

    secteur = state.config.secteur or (state.fiche_entreprise or {}).get("secteur", "autre")
    type_page = state.type_page or "article"

    try:
        html = state.brouillon_html or ""
        texte = _strip_html(html, 8000)

        # 1. Moteur de regles deterministe
        conformite = _check_rules(texte, secteur, type_page)

        # 2. Verification LLM pour les secteurs a risque eleve/critique
        if conformite.risque_juridique in ("eleve", "critique") and not state.config.dry_run:
            try:
                factory = LLMFactory(
                    anthropic_api_key=config.ANTHROPIC_API_KEY,
                    openai_api_key=config.OPENAI_API_KEY,
                    deepseek_api_key=config.DEEPSEEK_API_KEY,
                    gemini_api_key=config.GEMINI_API_KEY,
                    ollama_base_url=config.OLLAMA_BASE_URL,
                    dry_run=False,
                )
                system_prompt = (
                    f"Tu es un expert en conformite juridique pour le secteur {secteur}. "
                    f"Verifie le contenu et identifie les risques juridiques, mentions "
                    f"manquantes, et contenus interdits. "
                    f"Retourne UNIQUEMENT un objet JSON, sans texte autour."
                )
                user_msg = (
                    f"Verifie la conformite de ce contenu pour le secteur {secteur}.\n\n"
                    f"**Texte :**\n{texte[:3000]}\n\n"
                    f"Retourne UNIQUEMENT un JSON avec :\n"
                    f'- mentions_obligatoires_manquantes: ["mention 1", ...]\n'
                    f'- avertissements_requis: ["avertissement 1", ...]\n'
                    f'- contenus_problematiques: ["probleme 1", ...]\n'
                    f'- risque_juridique: "faible|modere|eleve|critique"\n'
                    f'- valide: true/false'
                )
                llm_text, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt,
                    user_message=user_msg,
                    agent_id=agent_id,
                    temperature=0.2,
                    max_tokens=1000,
                )

                import json, re
                match = re.search(r"\{.*\}", llm_text, re.DOTALL)
                data = json.loads(match.group(0)) if match else {}

                # Fusionner avec les regles deterministes
                if data.get("mentions_obligatoires_manquantes"):
                    conformite.mentions_obligatoires.extend(
                        data["mentions_obligatoires_manquantes"]
                    )
                if data.get("avertissements_requis"):
                    conformite.avertissements_requis.extend(data["avertissements_requis"])
                if data.get("risque_juridique"):
                    # Prioriser le LLM s'il evalue plus haut
                    risques = {"faible": 0, "modere": 1, "eleve": 2, "critique": 3}
                    if risques.get(data["risque_juridique"], 0) > risques.get(conformite.risque_juridique, 0):
                        conformite.risque_juridique = data["risque_juridique"]
                if data.get("valide") is False:
                    conformite.valide = False

                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                result.model_used = "rules-only"
                result.tokens_input = 0
                result.tokens_output = 0
                result.cost_estimated = 0.0
        else:
            result.model_used = "dry-run" if state.config.dry_run else "rules-only"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0

        state.conformite_data = conformite.model_dump()
        result.data = state.conformite_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        conformite = ConformiteData(
            valide=False,
            risque_juridique="critique",
            regles_appliquees=[f"Erreur lors de l'analyse de conformite: {e}"],
        )
        state.conformite_data = conformite.model_dump()
        result.data = state.conformite_data
        result.status = AgentStatus.COMPLETED
        result.model_used = result.model_used or "fallback"
        result.error_message = str(e)

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    log_agent_completed(
        agent_id, agent_name, result.duration_ms,
        tokens_input=result.tokens_input or 0,
        tokens_output=result.tokens_output or 0,
        cost_estimated=result.cost_estimated or 0.0,
        prompt_version="v1",
        model_used=result.model_used or "inconnu",
    )
    state.last_completed_agent_id = agent_id
    return state


def _estimate_cost(model: str, tokens_input: int, tokens_output: int) -> float:
    from hermes.core.budget import BudgetTracker
    tracker = BudgetTracker(token_budget=0, cost_budget=0)
    return round(tracker.estimate_cost(model, tokens_input, tokens_output), 6)
