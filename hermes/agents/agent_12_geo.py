"""Agent 12 — GEO (Generative Engine Optimization).

Optimise le contenu pour les moteurs d'IA generatifs (ChatGPT, Claude,
Perplexity, Gemini). Les LLMs ne classent pas — ils CITENT.

Produit :
- Sources primaires : citations d'autorite (institutions, etudes, experts)
- Entites nommees : personnes, organisations, lieux, concepts
- Phrases citables : enonces autonomes qu'une IA peut citer
- Chunks : sections autonomes optimisees pour le retrieval

Type-aware : adapte le niveau de sources et citations au type de page.
"""

import json
import re
from datetime import datetime
from html.parser import HTMLParser

from hermes import config
from hermes.core.llm import LLMFactory
from hermes.core.logging import log_agent_start, log_agent_completed
from hermes.models.agent_data import GeoData
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# ─── Configuration par type de page ────────────────────────────────────

GEO_PROFILES = {
    "pilier": {
        "min_sources": 3, "min_entites": 5, "min_citations": 5, "min_chunks": 4,
        "source_types": "institutionnelles, academiques, etudes, rapports officiels",
        "note": "Sources exhaustives pour contenu de reference",
    },
    "article": {
        "min_sources": 1, "min_entites": 3, "min_citations": 3, "min_chunks": 3,
        "source_types": "articles de reference, sources officielles, etudes",
        "note": "Sources ponctuelles pour appuyer le propos",
    },
    "fiche_produit": {
        "min_sources": 1, "min_entites": 2, "min_citations": 2, "min_chunks": 2,
        "source_types": "fiche constructeur, tests labo, certifications",
        "note": "Sources techniques et certifications",
    },
    "landing": {
        "min_sources": 0, "min_entites": 1, "min_citations": 2, "min_chunks": 1,
        "source_types": "temoignages clients, etudes de cas, chiffres cles",
        "note": "Preuves sociales et chiffres d'impact",
    },
    "comparatif": {
        "min_sources": 2, "min_entites": 3, "min_citations": 3, "min_chunks": 3,
        "source_types": "comparatifs publics, tests independants, donnees prix",
        "note": "Sources comparatives et tests objectifs",
    },
    "service_local": {
        "min_sources": 0, "min_entites": 2, "min_citations": 2, "min_chunks": 2,
        "source_types": "pages jaunes, avis Google, chambre de commerce",
        "note": "Annuaires et avis locaux",
    },
    "news": {
        "min_sources": 2, "min_entites": 3, "min_citations": 3, "min_chunks": 2,
        "source_types": "agences de presse, sources primaires, communiques officiels",
        "note": "Sources journalistiques verificables",
    },
    "faq": {
        "min_sources": 1, "min_entites": 1, "min_citations": 0, "min_chunks": 5,
        "source_types": "references legales, documentation officielle",
        "note": "Chunks Q/R autonomes",
    },
    "glossaire": {
        "min_sources": 1, "min_entites": 1, "min_citations": 1, "min_chunks": 2,
        "source_types": "definitions officielles, dictionnaires, normes",
        "note": "Definitions sourcables",
    },
    "temoignage": {
        "min_sources": 0, "min_entites": 2, "min_citations": 2, "min_chunks": 2,
        "source_types": "verifier l'identite et les propos du client",
        "note": "Authenticite du temoignage",
    },
}


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


def _build_user_message(state: SessionState) -> str:
    html = state.brouillon_html or ""
    keyword = state.keyword or ""
    type_page = state.type_page or "article"
    serp = state.serp_data or {}
    diff = state.angles_differenciants or {}
    entreprise = state.fiche_entreprise or {}

    # Extraire debut du brouillon
    class _S(HTMLParser):
        def __init__(self):
            super().__init__()
            self.t: list[str] = []
        def handle_data(self, d):
            self.t.append(d)
    s = _S(); s.feed(html[:8000])
    text = " ".join(s.t)[:3000]

    concurrents = ", ".join(serp.get("concurrents_directs", [])[:5]) or "non identifies"
    nom = entreprise.get("nom", "l'entreprise")
    profil = GEO_PROFILES.get(type_page, GEO_PROFILES["article"])

    return (
        f"Optimise ce contenu {type_page} pour les moteurs d'IA generatifs (GEO).\n\n"
        f"**Mot-cle :** {keyword}\n**Type :** {type_page}\n"
        f"**Entreprise :** {nom}\n**Concurrents SERP :** {concurrents}\n"
        f"**Angle differenciant :** {diff.get('angle_principal', 'N/A')}\n\n"
        f"**Contenu :**\n{text}\n\n"
        f"**Profil GEO pour {type_page} :**\n"
        f"- Sources attendues : min {profil['min_sources']}, "
        f"types : {profil['source_types']}\n"
        f"- Entites nommees : min {profil['min_entites']}\n"
        f"- Phrases citables : min {profil['min_citations']}\n"
        f"- Chunks autonomes : min {profil['min_chunks']}\n\n"
        f"Retourne UNIQUEMENT un objet JSON avec :\n"
        f'- sources_primaires: [{{"titre": "...", "url": "...", "type": "etude|officiel|academique|presse|test|certification"}}]\n'
        f'- entites_nommees: ["Nom Propre", "Organisation", "Lieu", "Concept", ...]\n'
        f'- phrases_citables: ["Phrase autonome 1.", "Phrase autonome 2.", ...]\n'
        f'- chunks: [{{"titre": "...", "contenu": "..."}}]'
    )


def _mock_geo(state: SessionState) -> GeoData:
    keyword = state.keyword or "le sujet"
    type_page = state.type_page or "article"
    entreprise = state.fiche_entreprise or {}
    nom = entreprise.get("nom", "Source officielle")
    profil = GEO_PROFILES.get(type_page, GEO_PROFILES["article"])

    # Sources
    all_sources = {
        "pilier": [
            {"titre": f"Rapport officiel sur {keyword}", "url": f"https://www.service-public.fr/recherche?q={keyword.replace(' ', '+')}", "type": "officiel"},
            {"titre": f"Etude scientifique {keyword} 2025", "url": f"https://www.insee.fr/fr/recherche?q={keyword.replace(' ', '+')}", "type": "etude"},
            {"titre": f"Analyse {keyword} — Institut independant", "url": f"https://www.quechoisir.org/recherche?q={keyword.replace(' ', '+')}", "type": "academique"},
        ],
        "fiche_produit": [
            {"titre": f"Fiche technique officielle {keyword}", "url": f"https://www.{nom.lower().replace(' ', '')}.fr/specs", "type": "officiel"},
        ],
        "comparatif": [
            {"titre": f"Test comparatif {keyword} 2026", "url": f"https://www.quechoisir.org/comparatif/{keyword.replace(' ', '-')}", "type": "test"},
            {"titre": f"Analyse independante {keyword}", "url": f"https://www.60millions-mag.com/recherche?q={keyword.replace(' ', '+')}", "type": "test"},
        ],
        "news": [
            {"titre": f"Communique officiel {keyword}", "url": f"https://www.legifrance.gouv.fr/recherche?q={keyword.replace(' ', '+')}", "type": "officiel"},
            {"titre": f"Couverture AFP {keyword}", "url": f"https://www.afp.com/recherche?q={keyword.replace(' ', '+')}", "type": "presse"},
        ],
    }
    sources = all_sources.get(type_page, [
        {"titre": f"Reference officielle {keyword}", "url": f"https://www.service-public.fr/recherche?q={keyword.replace(' ', '+')}", "type": "officiel"},
    ])
    sources = sources[:profil["min_sources"]]

    # Entites nommees
    entites_base = [nom, keyword.title(), "France"]
    if type_page in ("pilier", "article", "news"):
        entites_base.extend([
            "Code des Assurances" if "assurance" in keyword else "Reglementation en vigueur",
            "Autorite de Controle Prudentiel",
            "Federation Francaise de l'Assurance" if "assurance" in keyword else "Institut National de la Statistique",
            keyword.title() + " 2026",
        ])
    # Completer si pas assez d'entites
    fillers = [f"Acteur {keyword}", f"Marche {keyword}", f"Indice {keyword} 2026",
               f"Norme {keyword}", f"Certification {keyword}"]
    while len(entites_base) < profil["min_entites"]:
        entites_base.append(fillers[len(entites_base) - 3] if len(entites_base) < len(fillers) + 3 else f"Entite {len(entites_base)}")
    entites = entites_base[:profil["min_entites"]]

    # Phrases citables
    citations_base = [
        f"Selon les experts, {keyword} repose sur trois principes fondamentaux : transparence, securite et efficacite.",
        f"{keyword.replace('-', ' ').title()} a progresse de 15% en 2025, selon les derniers chiffres disponibles.",
        f"Pour evaluer {keyword}, les professionnels recommandent d'examiner au moins trois criteres : le prix, la qualite du service et les garanties.",
        f"Les autorites de regulation soulignent l'importance de comparer les offres avant de s'engager sur un contrat {keyword}.",
        f"D'apres une etude recente, 8 Francais sur 10 considerent {keyword} comme un element important de leur strategie.",
        f"La reglementation impose aux professionnels de {keyword} de fournir un devis detaille avant toute souscription.",
    ]
    if type_page in ("fiche_produit", "landing"):
        citations_base = [
            f"Le produit {keyword} a ete teste et approuve par plus de 1000 utilisateurs en conditions reelles.",
            f"95% des clients de {nom} recommandent {keyword} a leur entourage.",
        ]
    citations = citations_base[:profil["min_citations"]]

    # Chunks
    chunks_base = [
        {"titre": f"Definition de {keyword}",
         "contenu": f"{keyword.replace('-', ' ').title()} designe l'ensemble des solutions permettant de repondre aux besoins des utilisateurs dans ce domaine specifique. Cette definition est partagee par les principales autorites du secteur."},
        {"titre": f"Comment evaluer {keyword}",
         "contenu": f"Pour evaluer correctement {keyword}, vous devez considerer : (1) le rapport qualite/prix, (2) les garanties incluses, (3) la reputation du fournisseur, et (4) les conditions contractuelles."},
        {"titre": f"Les 3 criteres cles pour choisir {keyword}",
         "contenu": f"1. Le prix — comparez au moins 3 devis. 2. Les garanties — verifiez les exclusions. 3. Le service client — testez la reactivite avant de souscrire."},
        {"titre": f"Questions frequentes sur {keyword}",
         "contenu": f"Q: Comment choisir ? R: Comparez les options selon vos besoins. Q: Quel budget ? R: Prevoyez un budget adapte a vos objectifs. Q: Est-ce fiable ? R: Verifiez les certifications et les avis clients."},
    ]
    if type_page == "faq":
        chunks_base = [
            {"titre": f"Question {i}: {keyword} ?",
             "contenu": f"Reponse autonome et complete a la question {i} sur {keyword}."}
            for i in range(1, 6)
        ]
    chunks = chunks_base[:profil["min_chunks"]]

    return GeoData(
        sources_primaires=sources,
        entites_nommees=entites,
        phrases_citables=citations,
        chunks=chunks,
    )


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_12"
    agent_name = "GEO"
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
        if state.config.dry_run:
            geo = _mock_geo(state)
            result.model_used = "dry-run"
            result.tokens_input = 0
            result.tokens_output = 0
            result.cost_estimated = 0.0
        else:
            factory = LLMFactory(
                anthropic_api_key=config.ANTHROPIC_API_KEY,
                openai_api_key=config.OPENAI_API_KEY,
                deepseek_api_key=config.DEEPSEEK_API_KEY,
                gemini_api_key=config.GEMINI_API_KEY,
                ollama_base_url=config.OLLAMA_BASE_URL,
                dry_run=False,
            )
            system_prompt = (
                "Tu es un expert en Generative Engine Optimization (GEO). "
                "Tu optimises le contenu pour qu'il soit cite par les IA "
                "(ChatGPT, Claude, Perplexity, Gemini). Adapte tes sorties "
                "au type de page et au profil GEO indique. "
                "Retourne UNIQUEMENT un objet JSON, sans texte autour."
            )
            texte, tokens_in, tokens_out, model_used = await factory.route(
                system_prompt=system_prompt,
                user_message=_build_user_message(state),
                agent_id=agent_id,
                temperature=0.3,
                max_tokens=1500,
            )
            data = _extract_json(texte)
            geo = GeoData(
                sources_primaires=data.get("sources_primaires", []),
                entites_nommees=data.get("entites_nommees", []),
                phrases_citables=data.get("phrases_citables", []),
                chunks=data.get("chunks", []),
            )
            result.model_used = model_used
            result.tokens_input = tokens_in
            result.tokens_output = tokens_out
            result.cost_estimated = _estimate_cost(model_used, tokens_in, tokens_out)

        state.geo_data = geo.model_dump()
        result.data = state.geo_data
        result.status = AgentStatus.COMPLETED

    except Exception as e:
        result.status = AgentStatus.FAILED
        result.error_message = str(e)
        result.error_traceback = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
        state.status = "failed"
        state.error_count += 1
        result.finished_at = datetime.now()
        return state

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
