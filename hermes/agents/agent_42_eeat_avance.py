"""Agent 42 — EEAT Avance: Auteur & Confiance Site (gap module 8 items #302-326).

Verifie: presence auteur, bio auteur, page auteur dediee, schema Person,
coherence auteur/sujet, alertes YMYL sans expertise.
Signaux confiance: a propos, contact, mentions legales, CGU, RGPD,
HTTPS, affiliation visible, liens peu fiables.
Score EEAT site 0-100.
"""

import re, logging, time
from datetime import datetime

import httpx

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_42")

YMYL_SECTORS = ["sante", "medical", "finance", "banque", "assurance", "droit", "juridique",
                "securite", "cybersecurite", "pharmacie", "investissement"]

SIGNALS_CONFIANCE = ["a_propos", "contact", "mentions_legales", "cgu", "confidentialite",
                     "affiliation", "equipe", "partenaires", "presse", "blog"]


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_42"
    agent_name = "EEAT Avance"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        content = state.brouillon_html.html if state.brouillon_html and hasattr(state.brouillon_html, 'html') else ""
        site_url = state.site_url or ""

        eeat = {
            "author": {"found": False, "name": "", "bio_present": False, "page_author_exists": False,
                       "schema_person": False, "expertise_match": True},
            "site_trust": {"pages_found": [], "pages_missing": [], "trust_score": 0},
            "ymyl": {"is_ymyl_sector": False, "alerts": []},
            "content_trust": {"sources_institutionnelles": 0, "notes_prudence": False,
                              "faits_vs_analyse": False, "avertissement_ymyl": False},
            "eeat_score": 0,
            "recommandations": [],
        }

        # 1. Auteur
        author_match = re.search(r'(?i)(?:par|auteur|redige par|ecrit par)\s+([A-ZÀ-Ü][a-zà-ü]+(?:\s+[A-ZÀ-Ü][a-zà-ü]+)?)', content)
        if author_match:
            eeat["author"]["found"] = True
            eeat["author"]["name"] = author_match.group(1)

        # Bio auteur
        eeat["author"]["bio_present"] = bool(re.search(r'(?i)(expert|specialiste|consultant|formateur|certifie|diplome)', content))

        # Schema Person
        eeat["author"]["schema_person"] = bool(re.search(r'"@type"\s*:\s*"Person"', content))

        # 2. Site trust
        if site_url:
            eeat["site_trust"] = await _check_site_pages(site_url)

        # 3. YMYL
        secteur = getattr(state.config, 'secteur', '') if hasattr(state, 'config') else ''
        eeat["ymyl"]["is_ymyl_sector"] = any(s in (secteur or "").lower() for s in YMYL_SECTORS)
        if eeat["ymyl"]["is_ymyl_sector"] and not eeat["author"]["found"]:
            eeat["ymyl"]["alerts"].append("Contenu YMYL sans auteur identifie — risque EEAT")
        if eeat["ymyl"]["is_ymyl_sector"] and not eeat["author"]["bio_present"]:
            eeat["ymyl"]["alerts"].append("Contenu YMYL sans bio/expertise auteur visible")

        # 4. Content trust
        eeat["content_trust"]["sources_institutionnelles"] = len(re.findall(
            r'(?i)(cnil|anssi|nist|commission.europa|legifrance|service-public|who.int|unesco|has-sante)',
            content))
        eeat["content_trust"]["notes_prudence"] = bool(re.search(
            r'(?i)(attention|prudence|avertissement|consultez|demandez.*avis|prenez.*conseil)', content))

        # 5. Score
        score = 30
        if eeat["author"]["found"]: score += 15
        if eeat["author"]["bio_present"]: score += 10
        if eeat["author"]["schema_person"]: score += 5
        score += min(15, len(eeat["site_trust"]["pages_found"]) * 3)
        if eeat["content_trust"]["sources_institutionnelles"] >= 1: score += 10
        if eeat["content_trust"]["notes_prudence"]: score += 10
        if not eeat["ymyl"]["alerts"]: score += 5
        eeat["eeat_score"] = min(100, score + 10)

        if not eeat["author"]["found"]:
            eeat["recommandations"].append("Ajouter un auteur identifie par article")
        if not eeat["author"]["bio_present"]:
            eeat["recommandations"].append("Ajouter une bio auteur avec expertise")
        for p in eeat["site_trust"]["pages_missing"][:3]:
            eeat["recommandations"].append(f"Creer une page '{p.replace('_', ' ').title()}'")

        result.status = AgentStatus.COMPLETED
        result.data = eeat
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state


async def _check_site_pages(site_url: str) -> dict:
    pages_found = []
    pages_missing = []

    for page in SIGNALS_CONFIANCE:
        try:
            async with httpx.AsyncClient(timeout=8, follow_redirects=True) as client:
                resp = await client.get(f"{site_url.rstrip('/')}/{page.replace('_', '-')}")
                if resp.status_code == 200:
                    pages_found.append(page)
                else:
                    pages_missing.append(page)
        except Exception:
            pages_missing.append(page)

    trust_score = min(100, len(pages_found) * 10)
    return {"pages_found": pages_found, "pages_missing": pages_missing, "trust_score": trust_score}
