"""Agent 07 — Template.

Choisit le squelette editorial adapte au type de page et a l'intention.
Non skippable — la structure est obligatoire avant la redaction.
Bibliotheque de templates integree, enrichissable par LLM.
"""

import json
import re
from datetime import datetime

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import Section, TemplateData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# ─── Bibliotheque de templates ─────────────────────────────────────────

TEMPLATES: dict[str, list[dict]] = {
    "article": [
        {"type": "h1", "titre": "[Titre principal]", "contenu_guide": "Titre accrocheur incluant le mot-cle principal. 50-65 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "intro", "titre": "Introduction", "contenu_guide": "Accroche + presentation du sujet + annonce du plan. 100-150 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "[Section 1 : Contexte]", "contenu_guide": "Poser le contexte. Pourquoi ce sujet est important. 200-300 mots.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "[Section 2 : Corps principal]", "contenu_guide": "Le coeur du sujet. Donnees, exemples, explications. 300-500 mots.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "[Section 3 : Approfondissement]", "contenu_guide": "Aller plus loin. Cas concrets, cas d'usage. 200-400 mots.", "obligatoire": True, "ordre": 4},
        {"type": "h2", "titre": "En bref", "contenu_guide": "Resume en 3-5 bullet points pour les lecteurs presses.", "obligatoire": False, "ordre": 5},
        {"type": "conclusion", "titre": "Conclusion", "contenu_guide": "Synthese + rappel du point cle + ouverture. 100-150 mots.", "obligatoire": True, "ordre": 6},
        {"type": "cta", "titre": "[CTA]", "contenu_guide": "Call-to-action adapte a l'intention du lecteur.", "obligatoire": False, "ordre": 7},
    ],
    "pilier": [
        {"type": "h1", "titre": "[Titre du guide complet]", "contenu_guide": "Titre exhaustif incluant le mot-cle. 50-65 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "intro", "titre": "Introduction", "contenu_guide": "Pourquoi ce guide existe + ce que le lecteur va apprendre. 150-200 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "Definition et principes cles", "contenu_guide": "Definir le sujet. Lexique si necessaire. 200-400 mots.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "Comment ca fonctionne", "contenu_guide": "Mecanisme, processus, etapes. Schemas si possible. 300-500 mots.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "Les avantages et inconvenients", "contenu_guide": "Tableau comparatif. Honnetete editoriale. 200-400 mots.", "obligatoire": True, "ordre": 4},
        {"type": "h2", "titre": "Comment choisir / Comparatif", "contenu_guide": "Criteres de choix, options, grille de decision. 300-500 mots.", "obligatoire": True, "ordre": 5},
        {"type": "h2", "titre": "Guide pas a pas", "contenu_guide": "Etapes numerotees et actionnables. 300-500 mots.", "obligatoire": True, "ordre": 6},
        {"type": "h2", "titre": "Erreurs a eviter", "contenu_guide": "Les pieges courants et comment les contourner. 200-300 mots.", "obligatoire": True, "ordre": 7},
        {"type": "h2", "titre": "FAQ", "contenu_guide": "5-8 questions/reponses. Repondre aux PAA de la SERP.", "obligatoire": True, "ordre": 8},
        {"type": "h2", "titre": "En bref", "contenu_guide": "Resume executif en 5 bullet points.", "obligatoire": True, "ordre": 9},
        {"type": "conclusion", "titre": "Conclusion et prochaines etapes", "contenu_guide": "Recap + recommandation personnalisee + CTA. 150-200 mots.", "obligatoire": True, "ordre": 10},
    ],
    "fiche_produit": [
        {"type": "h1", "titre": "[Nom du produit]", "contenu_guide": "Nom du produit + slogan. 40-60 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "intro", "titre": "Apercu", "contenu_guide": "Presentation rapide du produit + benefice principal. 80-120 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "Caracteristiques principales", "contenu_guide": "Liste a puces des features cles. 200-300 mots.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "Avantages", "contenu_guide": "Benefices pour l'utilisateur. 200-300 mots.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "Specifications techniques", "contenu_guide": "Tableau des specs. Dimensions, compatibilite, etc.", "obligatoire": False, "ordre": 4},
        {"type": "h2", "titre": "Avis clients", "contenu_guide": "Temoignages ou note moyenne. 100-200 mots.", "obligatoire": False, "ordre": 5},
        {"type": "h2", "titre": "FAQ", "contenu_guide": "3-5 questions frequentes sur le produit.", "obligatoire": True, "ordre": 6},
        {"type": "cta", "titre": "Acheter / Essayer", "contenu_guide": "Bouton d'achat ou CTA principal.", "obligatoire": True, "ordre": 7},
    ],
    "faq": [
        {"type": "h1", "titre": "[Sujet] : Questions frequentes", "contenu_guide": "Titre clair indiquant qu'il s'agit d'une FAQ.", "obligatoire": True, "ordre": 0},
        {"type": "intro", "titre": "Introduction", "contenu_guide": "Bref contexte. 50-80 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "[Categorie 1]", "contenu_guide": "3-5 questions/reponses. Format Q/R clair.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "[Categorie 2]", "contenu_guide": "3-5 questions/reponses.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "[Categorie 3]", "contenu_guide": "3-5 questions/reponses.", "obligatoire": False, "ordre": 4},
        {"type": "cta", "titre": "Vous avez d'autres questions ?", "contenu_guide": "Invitation a contacter ou a consulter d'autres ressources.", "obligatoire": True, "ordre": 5},
    ],
    "service_local": [
        {"type": "h1", "titre": "[Service] a [Ville/Region]", "contenu_guide": "Titre local incluant le lieu. 50-65 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "intro", "titre": "Introduction", "contenu_guide": "Presentation de l'entreprise locale. 100-150 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "Nos services", "contenu_guide": "Liste detaillee des prestations. 200-400 mots.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "Pourquoi nous choisir", "contenu_guide": "Arguments de vente locaux. Proximite, disponibilite, expertise. 200-300 mots.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "Notre zone d'intervention", "contenu_guide": "Quartiers, villes dessertes. Carte si possible. 100-200 mots.", "obligatoire": False, "ordre": 4},
        {"type": "h2", "titre": "Avis clients", "contenu_guide": "Temoignages de clients locaux. 100-200 mots.", "obligatoire": False, "ordre": 5},
        {"type": "h2", "titre": "FAQ", "contenu_guide": "3-5 questions locales.", "obligatoire": False, "ordre": 6},
        {"type": "cta", "titre": "Contact / Devis / RDV", "contenu_guide": "Coordonnees, formulaire, telephone.", "obligatoire": True, "ordre": 7},
    ],
    "comparatif": [
        {"type": "h1", "titre": "[Produit A] vs [Produit B] : le comparatif complet", "contenu_guide": "Titre mentionnant les 2+ elements compares. 50-70 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "intro", "titre": "Introduction", "contenu_guide": "Pourquoi comparer ces options + criteres. 100-150 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "Tableau comparatif", "contenu_guide": "Tableau recapitulatif des criteres. Prix, fonctionnalites, notes.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "[Option 1] en detail", "contenu_guide": "Analyse detaillee de la premiere option. 200-400 mots.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "[Option 2] en detail", "contenu_guide": "Analyse detaillee de la deuxieme option. 200-400 mots.", "obligatoire": True, "ordre": 4},
        {"type": "h2", "titre": "Les alternatives", "contenu_guide": "Autres options a considerer. 100-200 mots.", "obligatoire": False, "ordre": 5},
        {"type": "h2", "titre": "Notre avis", "contenu_guide": "Recommandation finale argumentee. 150-250 mots.", "obligatoire": True, "ordre": 6},
        {"type": "cta", "titre": "[CTA]", "contenu_guide": "Essayer, comparer, ou en savoir plus.", "obligatoire": True, "ordre": 7},
    ],
    "landing": [
        {"type": "h1", "titre": "[Titre principal + slogan]", "contenu_guide": "Accroche forte + benefice principal. 40-60 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "h2", "titre": "Votre defi / Votre besoin", "contenu_guide": "Identifier le probleme du lecteur. Empathie. 100-150 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "Notre solution", "contenu_guide": "Comment on resout le probleme. 150-250 mots.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "Pourquoi nous faire confiance", "contenu_guide": "Preuves sociales, certifications, chiffres. 150-200 mots.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "Ce que nos clients disent", "contenu_guide": "2-3 temoignages clients. 100-200 mots.", "obligatoire": False, "ordre": 4},
        {"type": "cta", "titre": "[CTA principal]", "contenu_guide": "Bouton d'action principal. Gros, visible.", "obligatoire": True, "ordre": 5},
        {"type": "cta", "titre": "[CTA secondaire]", "contenu_guide": "Alternative plus douce pour les indecis.", "obligatoire": False, "ordre": 6},
    ],
    "news": [
        {"type": "h1", "titre": "[Titre de l'actualite]", "contenu_guide": "Titre informatif, factuel. 50-70 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "intro", "titre": "L'essentiel", "contenu_guide": "Les 5W en 2-3 phrases. Qui, quoi, quand, ou, pourquoi. 80-100 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "[Contexte]", "contenu_guide": "Le contexte de l'actualite. 200-300 mots.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "[Details et analyse]", "contenu_guide": "Approfondissement. Chiffres, citations, sources. 200-400 mots.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "Ce que ca change", "contenu_guide": "Impact, consequences, perspectives. 150-250 mots.", "obligatoire": True, "ordre": 4},
        {"type": "conclusion", "titre": "En resume", "contenu_guide": "Recap + prochaines etapes. 80-100 mots.", "obligatoire": True, "ordre": 5},
    ],
    "glossaire": [
        {"type": "h1", "titre": "[Terme] : definition", "contenu_guide": "Le terme a definir en titre. 30-50 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "h2", "titre": "Definition", "contenu_guide": "Definition claire en 1-2 phrases. 50-80 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "Explication detaillee", "contenu_guide": "Developpement avec exemples. 150-300 mots.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "Termes associes", "contenu_guide": "Definitions courtes de 3-5 termes lies. 100-200 mots.", "obligatoire": False, "ordre": 3},
        {"type": "h2", "titre": "Pour aller plus loin", "contenu_guide": "Liens vers ressources complementaires. 50-100 mots.", "obligatoire": False, "ordre": 4},
    ],
    "temoignage": [
        {"type": "h1", "titre": "[Client] : son experience avec [Produit/Service]", "contenu_guide": "Titre personnalise. 50-70 caracteres.", "obligatoire": True, "ordre": 0},
        {"type": "intro", "titre": "Portrait", "contenu_guide": "Qui est le client. Contexte, besoin initial. 80-120 mots.", "obligatoire": True, "ordre": 1},
        {"type": "h2", "titre": "Le defi", "contenu_guide": "Le probleme rencontre avant la solution. 150-200 mots.", "obligatoire": True, "ordre": 2},
        {"type": "h2", "titre": "La solution", "contenu_guide": "Comment le produit/service a resolu le probleme. 200-300 mots.", "obligatoire": True, "ordre": 3},
        {"type": "h2", "titre": "Les resultats", "contenu_guide": "Resultats chiffres, benefices obtenus. 150-250 mots.", "obligatoire": True, "ordre": 4},
        {"type": "cta", "titre": "Vous aussi, passez a l'action", "contenu_guide": "Invitation a reproduire le succes. 50-80 mots.", "obligatoire": True, "ordre": 5},
    ],
}


def _select_template(type_page: str, intention: str, keyword: str = "", serp_data: dict | None = None) -> TemplateData:
    """Selectionne le template adapte au type de page.

    Priorite : type_page explicite > intention deduite > article par defaut.
    Si le type_page n'est pas dans la bibliotheque, on utilise un template
    generique enrichi par le contexte.
    """
    # Mapping type_page → template_id
    template_id = type_page if type_page in TEMPLATES else "article"

    # Ajustements selon l'intention
    if intention == "transactionnelle" and type_page == "pilier":
        template_id = "landing"

    sections_raw = TEMPLATES.get(template_id, TEMPLATES["article"])

    # Enrichir les titres avec le mot-cle si fourni
    enriched = []
    for s in sections_raw:
        section = dict(s)
        if keyword and "[" in section.get("titre", ""):
            section["titre"] = section["titre"].replace("[Titre", f"[{keyword}")
            section["titre"] = section["titre"].replace("[Nom du produit]", keyword)
            section["titre"] = section["titre"].replace("[Sujet]", keyword)
            section["titre"] = section["titre"].replace("[Terme]", keyword)
        enriched.append(section)

    sections = [
        Section(
            type=s["type"],
            titre=s["titre"],
            contenu_guide=s["contenu_guide"],
            obligatoire=s.get("obligatoire", True),
            ordre=s.get("ordre", i),
        )
        for i, s in enumerate(enriched)
    ]

    return TemplateData(
        template_id=template_id,
        nom=f"Template {template_id.replace('_', ' ').title()}",
        structure=sections,
        nb_sections=len(sections),
        notes=f"Template {template_id} selectionne pour type_page={type_page}, intention={intention}.",
    )


def _extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except json.JSONDecodeError: pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(0))
        except json.JSONDecodeError: pass
    try: return json.loads(text.strip())
    except json.JSONDecodeError: pass
    return {}


def _build_llm_message(state: SessionState) -> str:
    keyword = state.keyword or ""
    type_page = state.type_page or "article"
    intention = state.intention or "informative"
    serp = state.serp_data or {}
    offre = state.offre_conversion_data or {}

    top_titles = "\n".join(
        f"  #{r.get('position', i+1)}: {r.get('title', '')[:100]}"
        for i, r in enumerate(serp.get("top10", [])[:5])
    ) or "N/A"

    return (
        f"Propose une structure editoriale optimale.\n\n"
        f"**Mot-cle :** {keyword}\n"
        f"**Type de page :** {type_page}\n"
        f"**Intention :** {intention}\n"
        f"**CTA principal :** {offre.get('cta_principal', 'N/A')}\n\n"
        f"**Top 5 SERP :**\n{top_titles}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f'- template_id: "{type_page}"\n'
        f'- nom: "Nom du template"\n'
        f'- structure: [{{"type": "h1"|"h2"|"h3"|"intro"|"conclusion"|"faq"|"cta"|"en_bref", "titre": "...", "contenu_guide": "...", "obligatoire": true|false, "ordre": 0}}]\n'
        f'- nb_sections: N\n'
        f'- notes: "Notes sur les choix editoriaux"'
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_07"
    agent_name = "Template"
    start_time = datetime.now()

    log_agent_start(agent_id, agent_name)

    result = state.agent_results.get(agent_id)
    if result is None:
        result = AgentResult(agent_id=agent_id, agent_name=agent_name)
        state.agent_results[agent_id] = result

    result.status = AgentStatus.RUNNING
    result.started_at = start_time
    result.prompt_version = "v1"

    try:
        type_page = state.type_page or "article"
        intention = state.intention or "informative"
        keyword = state.keyword or ""
        serp = state.serp_data

        if state.config.dry_run:
            template = _select_template(type_page, intention, keyword, serp)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            # Essayer d'abord la bibliotheque (deterministe, gratuit)
            template = _select_template(type_page, intention, keyword, serp)

            # Enrichir via LLM pour personnaliser les titres des sections
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
                    "Tu es un architecte editorial expert en SEO. "
                    "A partir du type de page et du mot-cle, tu enrichis "
                    "le template avec des titres de sections personnalises. "
                    "Retourne UNIQUEMENT un objet JSON, sans texte autour."
                )

                texte, tokens_in, tokens_out, model_used = await factory.route(
                    system_prompt=system_prompt,
                    user_message=_build_llm_message(state),
                    agent_id=agent_id,
                    temperature=0.3,
                    max_tokens=1000,
                )

                llm_data = _extract_json(texte)
                if llm_data.get("structure"):
                    # Fusionner : garder la structure de la bibliotheque mais
                    # remplacer les titres si le LLM en propose de meilleurs
                    llm_sections = llm_data["structure"]
                    for i, s in enumerate(template.structure):
                        if i < len(llm_sections) and llm_sections[i].get("titre"):
                            s.titre = llm_sections[i]["titre"]
                        if i < len(llm_sections) and llm_sections[i].get("contenu_guide"):
                            s.contenu_guide = llm_sections[i]["contenu_guide"]

                result.model_used = model_used
                result.tokens_input = tokens_in
                result.tokens_output = tokens_out
                result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)
            except Exception:
                # LLM indisponible, on garde la bibliotheque
                result.model_used = "library-only"

        state.template_data = template.model_dump()
        result.data = state.template_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        # Fallback ultime : article generique
        template = _select_template("article", "informative", state.keyword or "")
        state.template_data = template.model_dump()
        result.data = state.template_data
        result.status = AgentStatus.COMPLETED
        result.model_used = "fallback"
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
