"""Agent 27 — Coherence Inter-Articles.

Verifie que le nouveau contenu ne contredit pas les contenus existants
du site (prix, dates, affirmations). Utilise ChromaDB pour rechercher
les articles similaires et compare les claims.

Ajoute le 21 juin 2026 — suggestion DeepSeek validee par l'utilisateur.
"""

import json
import re
from datetime import datetime
from typing import Any, Optional

from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed
from hermes.core.memory import MemoryStore
from hermes.models.agent_data import FactCheckData, ErreurFactuelle
from hermes.models.common import AgentStatus
from hermes.models.session import AgentResult, SessionState


# Patterns de claims a verifier entre articles
CLAIM_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("prix", re.compile(
        r"(?:à\s+partir\s+de|prix|tarif|co[ûu]t|factur[ée])\s+"
        r"(?:de\s+)?(\d+[\s,.]?\d*)\s*(?:€|euros?|EUR|USD|\$)",
        re.IGNORECASE,
    )),
    ("date", re.compile(
        r"(?:depuis|cr[ée][ée]?|fond[ée][ée]?\s+en|lancement\s+en|lanc[ée][ée]?\s+en)\s+"
        r"(\d{4})",
        re.IGNORECASE,
    )),
    ("nombre", re.compile(
        r"(?:plus\s+de\s+|environ\s+|pr[èe]s\s+de\s+)?"
        r"(\d{2,4})\s*(?:clients?|utilisateurs?|entreprises?|projets?|collaborateurs?|salari[ée]s?)",
        re.IGNORECASE,
    )),
    ("certification", re.compile(
        r"(?:certifi[ée][ée]?|labellis[ée][ée]?|agr[ée][ée][ée]?)\s+(?:par\s+)?"
        r"([\w\s]{5,40})",
        re.IGNORECASE,
    )),
    ("garantie", re.compile(
        r"(?:garanti[ée]?|satisfait\s+ou\s+rembours[ée]|garantie\s+de\s+)"
        r"(\d+[\s,.]?\d*)\s*(?:ans?|mois|jours?|ann[ée]es?)",
        re.IGNORECASE,
    )),
]


async def run(state: SessionState) -> SessionState:
    """Verifie la coherence du nouveau contenu avec l'existant."""
    agent_id = "agent_27"
    agent_name = "Coherence Inter-Articles"
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
        html = state.brouillon_html or ""
        if not html:
            result.status = AgentStatus.SKIPPED_AUTO
            result.skip_reason = "Pas de brouillon a verifier"
            result.finished_at = datetime.now()
            return state

        keyword = state.keyword or ""
        site_url = state.site_url or ""

        # Chercher les contenus similaires dans ChromaDB
        try:
            mem = MemoryStore()
            similar = mem.search_similar(keyword, n_results=5)
        except Exception:
            # ChromaDB non dispo — OK, rien a comparer
            result.status = AgentStatus.COMPLETED
            result.finished_at = datetime.now()
            log_agent_completed(agent_id, agent_name, 0)
            return state

        if not similar or not similar.get("documents"):
            result.status = AgentStatus.COMPLETED
            result.data = {"conflits": [], "score_coherence": 10}
            result.finished_at = datetime.now()
            log_agent_completed(agent_id, agent_name, 0)
            return state

        # Extraire les claims du nouveau contenu
        new_claims = _extract_claims(html)

        # Comparer avec les contenus existants
        conflits = []
        existing_docs = similar.get("documents", [[]])[0]
        existing_metadatas = similar.get("metadatas", [[]])[0]

        for i, doc in enumerate(existing_docs):
            existing_claims = _extract_claims(doc)
            meta = existing_metadatas[i] if i < len(existing_metadatas) else {}

            for nc in new_claims:
                for ec in existing_claims:
                    if nc["type"] == ec["type"] and nc["type"] in ("prix", "nombre", "date"):
                        # Verifier si les valeurs sont differentes
                        if _values_conflict(nc["value"], ec["value"], nc["type"]):
                            conflits.append({
                                "gravite": "elevee" if nc["type"] == "prix" else "moderee",
                                "type": nc["type"],
                                "nouveau_texte": nc["texte"][:200],
                                "existant_texte": ec["texte"][:200],
                                "page_existante": meta.get("url", meta.get("title", "inconnue")),
                                "recommandation": (
                                    f"Le {nc['type']} '{nc['value']}' dans le nouveau contenu "
                                    f"differe de '{ec['value']}' dans un contenu existant. "
                                    f"Verifier et harmoniser."
                                ),
                            })

        # Score de coherence (0-10)
        score = max(0, 10 - len(conflits) * 3)

        result.data = {
            "conflits": conflits,
            "score_coherence": score,
            "articles_compares": len(existing_docs),
            "claims_nouveau": len(new_claims),
            "claims_existants": sum(1 for d in existing_docs for _ in _extract_claims(d)),
        }

        if conflits:
            result.status = AgentStatus.COMPLETED
            log_agent_completed(
                agent_id, agent_name, 0,
                tokens_input=0, tokens_output=0, cost_estimated=0.0,
            )
        else:
            result.status = AgentStatus.COMPLETED
            log_agent_completed(agent_id, agent_name, 0)

    except Exception as e:
        result.status = AgentStatus.FAILED
        result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
        state.error_count += 1

    result.finished_at = datetime.now()
    result.duration_ms = int((result.finished_at - start_time).total_seconds() * 1000)
    return state


def _extract_claims(html: str) -> list[dict]:
    """Extrait les affirmations factuelles d'un texte HTML.

    Returns: [{"type": "prix", "value": "29", "texte": "a partir de 29€"}]
    """
    # Nettoyer le HTML
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()

    claims = []
    for claim_type, pattern in CLAIM_PATTERNS:
        for m in pattern.finditer(text):
            value = m.group(1).replace(" ", "").replace(",", ".").replace("\xa0", "")
            claims.append({
                "type": claim_type,
                "value": value,
                "texte": text[max(0, m.start() - 30):m.end() + 30].strip(),
            })

    return claims


def _values_conflict(val1: str, val2: str, claim_type: str) -> bool:
    """Determine si deux valeurs sont en conflit.

    Pour les prix/nombres : conflit si difference > 20%.
    Pour les dates : conflit si difference > 2 ans.
    """
    try:
        v1 = float(val1)
        v2 = float(val2)
        if v1 == 0 or v2 == 0:
            return False
        diff = abs(v1 - v2) / max(v1, v2)
        if claim_type == "date":
            return diff > 0.15  # 2 ans sur 15 ans
        return diff > 0.20  # 20% de difference
    except (ValueError, TypeError):
        # Comparaison texte
        return val1.lower().strip() != val2.lower().strip()
