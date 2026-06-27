"""Agent 38 — Structure de Page par Type de Contenu (gap module 5).

Verifie que chaque article respecte la structure obligatoire selon son type.
8 types: news, analyse, pilier, comparatif, fiche_outil, service, categorie, article.
Bloque la publication si la structure minimale n'est pas respectee.
Score de structure 0-100 par type.

Base sur le document 630, items #177-185.
"""

import re, logging, time
from datetime import datetime
from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_38")

# Structure obligatoire par type de contenu
PAGE_STRUCTURE = {
    "news": {
        "required": ["intro_directe", "contexte", "impact"],
        "bonus": ["source", "limites", "chiffre_cle"],
        "min_words": 400,
        "min_h2": 3,
    },
    "analyse": {
        "required": ["problematique", "analyse", "cas_usage", "recommandation"],
        "bonus": ["donnees", "source", "avis_expert"],
        "min_words": 800,
        "min_h2": 4,
    },
    "pilier": {
        "required": ["intro", "sommaire", "corps", "faq", "conclusion"],
        "bonus": ["tableau", "checklist", "sources", "definition"],
        "min_words": 1500,
        "min_h2": 6,
        "faq_questions_min": 5,
    },
    "comparatif": {
        "required": ["intro", "tableau_comparatif", "cas_usage", "alternatives", "verdict"],
        "bonus": ["prix", "donnees", "faq"],
        "min_words": 1000,
        "min_h2": 5,
    },
    "fiche_outil": {
        "required": ["verdict", "pour_qui", "limites", "prix"],
        "bonus": ["donnees", "alternatives", "faq", "captures"],
        "min_words": 800,
        "min_h2": 4,
    },
    "page_service": {
        "required": ["promesse", "preuve", "processus", "cta"],
        "bonus": ["temoignages", "faq", "garantie"],
        "min_words": 500,
        "min_h2": 3,
    },
    "page_categorie": {
        "required": ["intro_editoriale", "filtres", "liens_articles"],
        "bonus": ["faq", "liens_piliers", "definition"],
        "min_words": 300,
        "min_h2": 2,
    },
    "article": {
        "required": ["intro", "corps", "conclusion"],
        "bonus": ["faq", "sources", "donnees", "definition"],
        "min_words": 800,
        "min_h2": 3,
    },
}


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_38"
    agent_name = "Structure par Type"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        type_page = state.type_page or "article"
        rules = PAGE_STRUCTURE.get(type_page, PAGE_STRUCTURE["article"])

        audit = {
            "type_page": type_page,
            "rules_applied": rules,
            "checks": {},
            "score": 100,
            "publishable": True,
            "blockers": [],
            "recommandations": [],
        }

        # 1. Word count
        wc = len(re.findall(r"\b\w+\b", content))
        audit["checks"]["word_count"] = {"value": wc, "min": rules["min_words"],
                                          "passed": wc >= rules["min_words"]}
        if not audit["checks"]["word_count"]["passed"]:
            audit["blockers"].append(f"Contenu trop court: {wc}/{rules['min_words']} mots")
            audit["publishable"] = False
            audit["score"] -= 20

        # 2. H2 count
        h2_count = len(re.findall(r"<h2[^>]*>", content, re.IGNORECASE))
        audit["checks"]["h2_count"] = {"value": h2_count, "min": rules["min_h2"],
                                       "passed": h2_count >= rules["min_h2"]}
        if not audit["checks"]["h2_count"]["passed"]:
            audit["blockers"].append(f"Pas assez de H2: {h2_count}/{rules['min_h2']}")
            audit["score"] -= 15

        # 3. FAQ (required on pilier)
        if "faq" in rules.get("required", []):
            faq_section = bool(re.search(r'(?i)faq|foire.*questions|questions.*reponses', content))
            faq_count = len(re.findall(r'(?i)<h[23][^>]*>(?:[^<]*\?)[^<]*</h[23]>', content))
            audit["checks"]["faq"] = {"questions_found": faq_count,
                                      "min_required": rules.get("faq_questions_min", 3),
                                      "passed": faq_count >= rules.get("faq_questions_min", 3)}
            if not audit["checks"]["faq"]["passed"]:
                audit["blockers"].append(f"FAQ insuffisante: {faq_count}/{rules['faq_questions_min']} questions")
                audit["score"] -= 20

        # 4. Check structure elements
        for elem in rules["required"]:
            found = _detect_element(content, elem)
            audit["checks"][elem] = {"found": found}
            if not found:
                audit["blockers"].append(f"Element obligatoire manquant: {elem}")
                audit["score"] -= 10

        # 5. Bonus elements
        for elem in rules.get("bonus", []):
            found = _detect_element(content, elem)
            if found:
                audit["score"] += 3

        audit["score"] = max(0, min(100, audit["score"]))
        if audit["score"] < 50:
            audit["publishable"] = False

        result.status = AgentStatus.COMPLETED
        result.data = audit
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state


def _detect_element(content: str, elem: str) -> bool:
    """Detecte la presence d'un element structurel dans le contenu."""
    patterns = {
        "intro_directe": r"<p[^>]*>.*?</p>",  # First paragraph exists
        "contexte": r"(?i)(contexte|situation|enjeu|pourquoi|probleme)",
        "impact": r"(?i)(impact|consequence|effet|resultat|bilan)",
        "problematique": r"(?i)(problematique|question|enjeu|defi)",
        "analyse": r"(?i)(analyse|decryptage|examen|etude)",
        "cas_usage": r"(?i)(cas d'?usage|exemple concret|application|mise en (oe|œ)uvre)",
        "recommandation": r"(?i)(recommand|conseil|preconis|a faire)",
        "intro": r"<h1[^>]*>.*</h1>\s*<p[^>]*>",
        "sommaire": r"(?i)(sommaire|table des mati|au programme|dans cet article)",
        "corps": r"<h2[^>]*>",  # At least one H2
        "faq": r"(?i)(faq|foire aux questions|questions.*reponses)",
        "conclusion": r"(?i)(conclusion|en resume|pour conclure|bilan|recapitul)",
        "tableau_comparatif": r"<table[^>]*>",
        "alternatives": r"(?i)(alternative|concurrent|autre solution|vs|versus)",
        "verdict": r"(?i)(verdict|notre avis|recommandation finale|lequel choisir)",
        "pour_qui": r"(?i)(pour qui|cible|public|destine)",
        "limites": r"(?i)(limite|attention|inconvenient|point faible|ne convient pas)",
        "prix": r"(?i)(prix|tarif|cout|abonnement|gratuit|euros?)",
        "promesse": r"(?i)(promesse|garantie|engagement|valeur|benefice)",
        "preuve": r"(?i)(preuve|temoignage|client|resultat|chiffre|etude de cas)",
        "processus": r"(?i)(processus|methode|etape|comment ca marche|fonctionnement)",
        "cta": r"(?i)(contact|devis|demo|essai|rdv|commander|inscription)",
        "filtres": r"(?i)(filtre|categorie|tag|tri)",
        "liens_articles": r"<a[^>]+href=[\"'][^\"']*/(?:blog|article|news|post)/",
        "donnees": r"(?i)(donnee|statistique|chiffre|pourcentage|\d+%)",
        "source": r"(?i)(source|reference|selon|d'apres)",
        "definition": r"(?i)(definition|qu'est-ce|c'est quoi|signifie|designer)",
        "checklist": r"(?i)(checklist|liste|a faire|points cles)",
        "tableau": r"<table[^>]*>",
        "temoignages": r"(?i)(temoignage|avis client|ils nous font confiance)",
        "captures": r"<img[^>]*>",
        "garantie": r"(?i)(garantie|satisfait|rembourse|essai gratuit)",
    }
    pat = patterns.get(elem)
    if not pat:
        return True  # Element non critique, on laisse passer
    return bool(re.search(pat, content, re.IGNORECASE))
