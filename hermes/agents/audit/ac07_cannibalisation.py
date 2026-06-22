"""AC07 — Cannibalisation Inter-Pages.

Detecte les paires de pages qui ciblent les memes intentions.
Utilise similarite cosinus entre titres + H2.
Deterministe (pas de LLM). Skippable si < 2 pages auditees.
"""

import re
from collections import Counter
from datetime import datetime
from math import sqrt

from hermes.models.audit import AuditSessionState


def _cosine_similarity(vec1: dict, vec2: dict) -> float:
    """Calcule la similarite cosinus entre deux vecteurs TF."""
    if not vec1 or not vec2:
        return 0.0
    all_keys = set(vec1) | set(vec2)
    dot = sum(vec1.get(k, 0) * vec2.get(k, 0) for k in all_keys)
    norm1 = sqrt(sum(v ** 2 for v in vec1.values()))
    norm2 = sqrt(sum(v ** 2 for v in vec2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _tf_vector(text: str) -> dict:
    """Vecteur TF brut depuis un texte."""
    words = re.findall(r"\b\w{4,}\b", text.lower())
    stopwords = {
        "dans", "pour", "avec", "sur", "sont", "pas", "une", "est", "que", "qui",
        "les", "des", "aux", "ces", "son", "ses", "cette", "leur", "leurs",
        "tout", "tous", "plus", "peut", "fait", "faire", "etre", "avoir", "aussi",
        "comme", "bien", "entre", "nous", "vous", "nos", "vos",
    }
    words = [w for w in words if w not in stopwords]
    return dict(Counter(words))


async def run(state: AuditSessionState) -> AuditSessionState:
    """Detecte les paires cannibales entre les pages auditees."""
    state.current_agent = "ac07"

    if len(state.crawled_pages) < 2:
        state.cannibalisation = []
        return state

    pages = [p for p in state.crawled_pages if not p.fetch_error]
    if len(pages) < 2:
        state.cannibalisation = []
        return state

    cannibal_pairs = []
    seen = set()

    for i, p1 in enumerate(pages):
        text1 = f"{p1.title} {' '.join(p1.h2_list[:10])}"
        vec1 = _tf_vector(text1)

        for j, p2 in enumerate(pages):
            if i >= j:
                continue
            pair_key = (min(p1.url, p2.url), max(p1.url, p2.url))
            if pair_key in seen:
                continue
            seen.add(pair_key)

            text2 = f"{p2.title} {' '.join(p2.h2_list[:10])}"
            vec2 = _tf_vector(text2)
            sim = _cosine_similarity(vec1, vec2)

            if sim > 0.65:
                action = "differentier"
                if sim > 0.85:
                    action = "fusionner"
                elif sim > 0.75:
                    action = "reviser_angle"

                cannibal_pairs.append({
                    "page1": p1.url,
                    "page2": p2.url,
                    "similarite": round(sim, 3),
                    "action": action,
                    "h1_p1": p1.h1[:80],
                    "h1_p2": p2.h1[:80],
                })

    state.cannibalisation = cannibal_pairs
    state.updated_at = datetime.now()
    return state
