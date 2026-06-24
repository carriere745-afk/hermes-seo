"""ST02 — Detection de Cannibalisation.

Croise les positions P4 avec ChromaDB pour detecter les pages qui se cannibalisent.
Attribue une gravite (critical/high/medium/low) basee sur le chevauchement semantique.
Non skippable. $0 — pas de LLM.
"""

import logging
import math
import time
from collections import defaultdict
from datetime import datetime

from hermes.models.strategie import StrategieState
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st02")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st02"
    state.phase = "analyse"

    cannibalisations: list[dict] = []

    # Charger les positions P4
    p4_positions = _load_p4_positions()

    if p4_positions:
        cannibalisations = _detect_cannibalisation(p4_positions, state)
    else:
        # Mode degrade : utiliser les sujets de ST01
        cannibalisations = _detect_cannibalisation_from_sujets(state.sujets)

    # Enrichir avec ChromaDB si disponible
    try:
        _enrich_with_similarity(cannibalisations)
    except Exception as e:
        logger.warning(f"ST02: ChromaDB enrichment failed ({e})")

    state.cannibalisations = cannibalisations
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st02", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    n_critical = sum(1 for c in cannibalisations if c.get("gravite") == "critical")
    logger.info(f"ST02: {len(cannibalisations)} cannibalisations detectees — {n_critical} critiques")
    return state


def _load_p4_positions() -> list[dict]:
    try:
        from pathlib import Path
        import sqlite3
        db_path = Path("data/serp_visibility.db")
        if not db_path.exists():
            return []
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT keyword, url, AVG(position) as avg_pos "
            "FROM positions_history "
            "WHERE date >= date('now', '-30 days') "
            "GROUP BY keyword, url "
            "HAVING AVG(position) <= 20 "
            "ORDER BY avg_pos"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _detect_cannibalisation(positions: list[dict], state: StrategieState) -> list[dict]:
    """Detecte les keywords pour lesquels plusieurs URLs du meme site rankent."""
    by_keyword: dict[str, list[dict]] = defaultdict(list)
    domain = state.domain

    for p in positions:
        url = p.get("url", "")
        if domain and domain in url:
            kw = p.get("keyword", "")
            by_keyword[kw].append(p)

    results = []
    for kw, entries in by_keyword.items():
        if len(entries) >= 2:
            sorted_entries = sorted(entries, key=lambda e: e.get("avg_pos", 100))
            pos_diff = abs(sorted_entries[0]["avg_pos"] - sorted_entries[1]["avg_pos"])
            gravite = _compute_gravite(len(entries), pos_diff)
            results.append({
                "keyword": kw,
                "pages_concernees": [e["url"] for e in sorted_entries],
                "positions": [e["avg_pos"] for e in sorted_entries],
                "gravite": gravite,
                "recommandation": _recommandation_cannib(gravite, sorted_entries),
                "n_pages": len(entries),
            })
    return results


def _detect_cannibalisation_from_sujets(sujets: list) -> list[dict]:
    """Fallback: detecte les sujets avec keywords similaires."""
    from collections import Counter
    results = []
    all_keywords = []
    for s in sujets:
        all_keywords.extend(s.keywords if hasattr(s, 'keywords') else [])

    word_counts = Counter()
    for kw in all_keywords:
        for word in kw.split():
            if len(word) > 3:
                word_counts[word] += 1

    # Keywords partageant les memes mots frequents = cannibalisation potentielle
    for word, count in word_counts.most_common(20):
        if count >= 2:
            shared = [kw for kw in all_keywords if word in kw]
            if len(shared) >= 2:
                results.append({
                    "keyword": word,
                    "pages_concernees": shared,
                    "positions": [],
                    "gravite": "low",
                    "recommandation": "Verifier si les pages ciblant ces mots-cles se concurrencent",
                    "n_pages": len(shared),
                })
    return results[:20]


def _compute_gravite(n_pages: int, pos_diff: float) -> str:
    if n_pages >= 3 and pos_diff < 3:
        return "critical"
    elif pos_diff < 5:
        return "high"
    elif pos_diff < 10:
        return "medium"
    return "low"


def _recommandation_cannib(gravite: str, entries: list) -> str:
    if gravite == "critical":
        return "Fusionner les pages ou creer un pilier avec redirections"
    elif gravite == "high":
        return "Differencier les intentions ou consolider le contenu"
    elif gravite == "medium":
        return "Surveiller. Si les positions se degradent, envisager la fusion"
    return "Pas d'action immediate necessaire"


def _enrich_with_similarity(cannibalisations: list[dict]) -> None:
    """Tente d'enrichir avec ChromaDB pour mesurer la similarite semantique."""
    try:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(
            path="data/chroma",
            settings=Settings(anonymized_telemetry=False),
        )
        try:
            collection = client.get_collection("hermes_pages")
            for c in cannibalisations:
                pages = c.get("pages_concernees", [])
                if len(pages) >= 2:
                    try:
                        results = collection.get(ids=pages[:2])
                        if results and results.get("embeddings") and len(results["embeddings"]) >= 2:
                            emb1 = results["embeddings"][0]
                            emb2 = results["embeddings"][1]
                            if emb1 and emb2:
                                similarity = float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2) + 1e-10))
                                c["similarite_semantique"] = round(similarity, 3)
                                if similarity > 0.9:
                                    c["gravite"] = "critical"
                                    c["recommandation"] = "Pages quasi-identiques — fusion imperatives"
                    except Exception:
                        pass
        except Exception:
            pass
    except ImportError:
        pass

try:
    import numpy as np
except ImportError:
    np = None
