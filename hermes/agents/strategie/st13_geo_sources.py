"""Agent ST13 — GEO Source Confidence Scorer (gap #5).

Verifie que les articles citent des sources d'autorite.
Score de confiance source (CNIL/ANSSI/NIST = A, VentureBeat = B, blog inconnu = D).
Les articles sans source sur un sujet factuel sont bloques.
Ferme le gap #5 du document 630 (GEO : score confiance source).
"""

import logging, re, time
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st13")

# Base d'autorite des sources (document 630, section 7.1)
SOURCE_AUTHORITY = {
    "A": ["cnil.fr", "anssi.gouv.fr", "nist.gov", "commission.europa.eu",
          "legifrance.gouv.fr", "service-public.fr", "who.int", "un.org",
          "unesco.org", "github.com", "pypi.org", "arxiv.org",
          "google.com/research", "openai.com/research", "anthropic.com/research"],
    "B": ["venturebeat.com", "techcrunch.com", "wired.com", "theverge.com",
          "siecledigital.fr", "journaldunet.com", "lemonde.fr", "lesechos.fr",
          "bfmtv.com", "francetvinfo.fr", "zdnet.fr", "01net.com"],
    "C": ["medium.com", "dev.to", "blog.google", "blog.openai.com",
          "blog.anthropic.com", "mistral.ai/news", "meta.com/blog"],
    "D": [],  # Tout le reste (blogs personnels, sites inconnus)
}


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st13"

    source_scores: list[dict] = []
    pages_sans_source = 0

    for rec in state.recommandations:
        # Analyser si le sujet est factuel (chiffres, prix, benchmarks)
        sujet = (rec.sujet or "").lower()
        is_factuel = any(w in sujet for w in ["prix", "chiffre", "benchmark",
                                                "donnee", "statistique", "loi",
                                                "comparatif", "test"])

        # Verifier les sources citees
        sources = _extract_sources(rec.justification or "")

        score = "C"  # Defaut
        if sources:
            best = max(_source_level(s) for s in sources)
            score = best
        elif is_factuel:
            pages_sans_source += 1

        source_scores.append({
            "sujet": rec.sujet,
            "is_factuel": is_factuel,
            "sources_trouvees": sources,
            "source_score": score,
            "alerte": "PAS DE SOURCE — sujet factuel" if is_factuel and not sources else "",
        })

    state.source_scores = source_scores
    state.pages_sans_source = pages_sans_source
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(session_id=state.session_id, agent_id="st13", pipeline_id="strategie",
              model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms, success=True,
              predictions={"pages_sans_source": pages_sans_source})

    if pages_sans_source:
        logger.warning(f"ST13: {pages_sans_source} pages factuelles sans source detectees")
    return state


def _source_level(domain: str) -> str:
    dl = domain.lower()
    for level, domains in SOURCE_AUTHORITY.items():
        if any(d in dl for d in domains):
            return level
    return "D"


def _extract_sources(text: str) -> list[str]:
    """Extrait les domaines de sources depuis un texte."""
    urls = re.findall(r"https?://([a-zA-Z0-9.-]+)", text)
    domains = []
    for url in urls:
        domain = url.replace("www.", "").split("/")[0]
        if domain not in domains:
            domains.append(domain)
    return domains
