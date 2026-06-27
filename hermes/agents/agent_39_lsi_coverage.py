"""Agent 39 — LSI Keywords & Couverture Topique (gap module 5 items #152-157).

Analyse les mots-cles secondaires et entites liees (LSI) presents dans le contenu.
Compare avec le top 10 SERP pour identifier les mots-cles manquants.
Score de couverture topique: combien de sous-sujets sont couverts.
Suggere les sections manquantes vs contenu concurrent.
"""

import re, logging, time
from collections import Counter
from datetime import datetime

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_39")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_39"
    agent_name = "LSI & Couverture Topique"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        keyword = state.keyword or ""

        # 1. Extraire les mots-cles LSI du contenu
        lsi_keywords = _extract_lsi(content, keyword)

        # 2. Extraire les entites nommees
        named_entities = _extract_entities(content)

        # 3. Verifier les sections couvertes
        coverage = _check_coverage(content, keyword)

        # 4. Score
        score = _compute_lsi_score(lsi_keywords, named_entities, coverage)

        output = {
            "lsi_keywords": lsi_keywords[:15],
            "named_entities": named_entities[:10],
            "coverage": coverage,
            "lsi_score": score,
            "recommandations": [],
        }

        # Suggestions
        missing = coverage.get("missing_sections", [])
        if missing:
            output["recommandations"].append(f"Ajouter les sections: {', '.join(missing[:5])}")
        if len(lsi_keywords) < 5:
            output["recommandations"].append(f"Enrichir le champ lexical: seulement {len(lsi_keywords)} mots-cles LSI identifies")
        if len(named_entities) < 3:
            output["recommandations"].append("Ajouter des entites nommees (marques, personnes, organisations) pour le GEO")

        result.status = AgentStatus.COMPLETED
        result.data = output
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state


def _extract_lsi(content: str, kw: str) -> list[dict]:
    """Extrait les mots-cles LSI (co-occurrence avec le mot-cle principal)."""
    words = re.findall(r"\b\w{4,}\b", content.lower())
    stop = {"cette", "avec", "pour", "dans", "sont", "plus", "tout", "leur", "aussi",
            "ainsi", "alors", "bien", "etre", "avoir", "faire", "comme", "peut", "autre"}
    words = [w for w in words if w not in stop]

    # Trouver les mots proches du keyword
    kw_words = set(kw.lower().split())
    freq = Counter(w for w in words if w not in kw_words)

    return [{"word": w, "count": c, "density": round(c / max(len(words), 1) * 100, 1)}
            for w, c in freq.most_common(15)]


def _extract_entities(content: str) -> list[str]:
    """Extrait les entites nommees (majuscules, noms propres)."""
    # Noms propres: sequences de mots commencant par une majuscule
    entities = re.findall(r"\b([A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+){0,2})\b", content)
    # Filtrer les faux positifs (debuts de phrase)
    filtered = [e for e in entities if len(e) > 3 and not e.startswith(("Le ", "La ", "Les ", "Des ", "Un ", "Une "))]
    return list(set(filtered))[:15]


def _check_coverage(content: str, kw: str) -> dict:
    """Verifie quelles sections SEO sont couvertes dans le contenu."""
    sections = {
        "definition": r"(?i)(definition|qu'est-ce|c'est quoi|signifie|designe|designer)",
        "historique": r"(?i)(historique|evolution|origine|creation|fonde|date)",
        "avantages": r"(?i)(avantage|benefice|atout|point fort|gain)",
        "inconvenients": r"(?i)(inconvenient|limite|risque|danger|point faible)",
        "chiffres": r"(?i)(statistique|chiffre|pourcentage|donnee|\d+\s*%)",
        "comparaison": r"(?i)(compar|versus|vs\.|alternative|difference|par rapport)",
        "cas_pratique": r"(?i)(exemple|cas (d'|de )?(usage|pratique|concret)|application)",
        "temoignage": r"(?i)(temoignage|avis|experience|retour|client)",
        "prix": r"(?i)(prix|tarif|cout|gratuit|abonnement|\d+\s*euros?)",
        "tutoriel": r"(?i)(tutoriel|guide|comment faire|etape|pas a pas|methode)",
        "faq": r"(?i)(faq|question.*reponse|foire aux questions)",
        "sources": r"(?i)(source|reference|bibliographie|pour aller plus loin)",
        "conclusion": r"(?i)(conclusion|en resume|bilan|pour conclure|recapitul)",
        "cta": r"(?i)(contact|devis|demo|essai|rdv|inscription|telecharger)",
    }

    covered = []
    missing = []
    for name, pat in sections.items():
        if re.search(pat, content):
            covered.append(name)
        else:
            missing.append(name)

    coverage_pct = round(len(covered) / len(sections) * 100)
    return {"covered": covered, "missing_sections": missing,
            "coverage_pct": coverage_pct, "total_sections": len(sections)}


def _compute_lsi_score(lsi: list, entities: list, coverage: dict) -> int:
    score = 40  # Base
    score += min(30, len(lsi) * 2)
    score += min(15, len(entities) * 3)
    score += min(15, coverage.get("coverage_pct", 0) // 7)
    return min(100, score)
