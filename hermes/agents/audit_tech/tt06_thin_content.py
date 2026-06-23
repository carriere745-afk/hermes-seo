"""T06 — Thin Content & Duplication (adaptatif).

Detecte les contenus trop courts ou dupliques, en s'adaptant au type de page.

Seuils adaptatifs (word_count minimum) :
- Article / Pilier : 600 mots
- Fiche produit e-commerce : 300 mots
- Page categorie : 200 mots
- Page service : 400 mots
- Landing page : 350 mots
- Page FAQ : 150 mots par Q/R
- Page marque : 250 mots
- Page contact / CGU / Mentions legales / Panier / Login : PAS DE SEUIL

Detection de duplication :
- Exact match (MD5 hash) → confidence high
- Near-duplicate (cosinus > 0.90) → confidence high
- Near-duplicate (cosinus > 0.85) → confidence medium

do_not_recommend_if : ne pas recommander d'ajouter du contenu aux pages legal/login/panier.
$0 — pas de LLM.
"""

import hashlib
import logging
import re
from collections import Counter
from datetime import datetime
from urllib.parse import urlparse

import numpy as np

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt06")

# Seuils adaptatifs par type de page
THIN_CONTENT_THRESHOLDS = {
    "accueil": {"min_words": 200, "reason": "Page d'accueil — peut etre courte mais doit presenter le site"},
    "article": {"min_words": 600, "reason": "Article — le contenu principal doit etre substantiel"},
    "produit": {"min_words": 300, "reason": "Fiche produit e-commerce — courte mais doit etre complete"},
    "categorie": {"min_words": 200, "reason": "Page listing — le contenu est dans les produits"},
    "service": {"min_words": 400, "reason": "Page service — besoin de details pour convaincre"},
    "landing": {"min_words": 350, "reason": "Landing page — ciblee, courte par nature"},
    "faq": {"min_words": 150, "reason": "FAQ — une reponse courte peut etre valable"},
    "marque": {"min_words": 250, "reason": "Page marque — peut etre succincte"},
    "legale": {"min_words": 0, "reason": "Page legale — pas de seuil, volontairement courte"},
    "autre": {"min_words": 300, "reason": "Page non categorisee — seuil par defaut"},
}

# Types de page a ne jamais penaliser pour thin content
DO_NOT_PENALIZE = {"legale", "categorie"}

# Types de page a ne jamais recommander d'ajouter du contenu
DO_NOT_RECOMMEND = ["legale", "panier", "login", "compte"]


def _get_page_type(url: str, h1: str = "", title: str = "") -> str:
    """Determine le type de page a partir de son URL et contenu."""
    path = urlparse(url).path.lower()

    if path in ("/", ""):
        return "accueil"

    # Patterns explicites
    if re.search(r"/\d+-[\w-]+\.html?$", path):
        return "produit"
    if any(w in path for w in ("/blog/", "/article/", "/actualite/", "/news/", "/post/", "/module-blog")):
        return "article"
    if any(w in path for w in ("/produit/", "/product/", "/shop/")):
        return "produit"
    if any(w in path for w in ("/categorie/", "/category/", "/collection/")):
        return "categorie"
    if any(w in path for w in ("/service/", "/prestation/", "/offre/")):
        return "service"
    if any(w in path for w in ("/cgu/", "/cgv/", "/mentions/", "/privacy/", "/contact/", "/nous-contacter")):
        return "legale"
    if path.rstrip("/").endswith(("/cgu", "/cgv", "/mentions-legales", "/privacy", "/contact", "/nous-contacter")):
        return "legale"
    if any(w in path for w in ("/login", "/account", "/my-account", "/mon-compte", "/panier", "/cart", "/checkout")):
        return "legale"
    if any(w in path for w in ("/faq/", "/questions/", "/glossaire/")):
        return "faq"
    if any(w in path for w in ("/landing/", "/lp/", "/promo/")):
        return "landing"

    return "autre"


def _text_hash(text: str) -> str:
    """Calcule un hash MD5 du texte pour detection d'exacts duplicates."""
    cleaned = re.sub(r"\s+", " ", text.lower().strip())
    return hashlib.md5(cleaned.encode("utf-8")).hexdigest()


def _cosine_similarity(text1: str, text2: str) -> float:
    """Calcule la similarite cosinus entre deux textes (TF brut, sans IDF)."""
    words1 = re.findall(r"\w+", text1.lower())
    words2 = re.findall(r"\w+", text2.lower())

    if not words1 or not words2:
        return 0.0

    vocab = set(words1) | set(words2)
    vec1 = np.array([words1.count(w) for w in vocab])
    vec2 = np.array([words2.count(w) for w in vocab])

    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def _get_visible_text(page) -> str:
    """Reconstitue un texte visible a partir des signaux (title + h1 + meta)."""
    parts = []
    if page.title:
        parts.append(page.title)
    if page.meta_description:
        parts.append(page.meta_description)
    if page.h1:
        parts.append(page.h1)
    # H2s
    for h2 in page.h2_list[:5]:
        parts.append(h2)
    return " ".join(parts)


async def run(state: TechAuditState) -> TechAuditState:
    """Detecte thin content et duplication."""
    state.current_agent = "tt06"

    if not state.crawled_pages:
        logger.warning("T06: aucune page — skip")
        return state

    logger.info(f"T06: analysing thin content and duplication for {len(state.crawled_pages)} pages")

    issue_counter = len(state.issues)
    thin_count = 0
    dup_pairs = []

    # 1. Thin content detection
    for page in state.crawled_pages:
        if page.fetch_error or page.status_code != 200:
            continue

        page_type = _get_page_type(page.url, page.h1, page.title)
        threshold = THIN_CONTENT_THRESHOLDS.get(page_type, THIN_CONTENT_THRESHOLDS["autre"])

        # Skip si pas de seuil
        if threshold["min_words"] == 0:
            continue

        if page.word_count < threshold["min_words"]:
            # Verifier do_not_recommend
            do_not = []
            if page_type in DO_NOT_RECOMMEND:
                do_not.append(f"page_{page_type}")

            issue_counter += 1
            thin_count += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="content",
                description=f"Contenu court ({page.word_count} mots, seuil {threshold['min_words']} pour page {page_type}) — {threshold['reason']}",
                url=page.url,
                observed=f"word_count: {page.word_count}, page_type: {page_type}",
                rule=f"word_count >= {threshold['min_words']} pour type {page_type}",
                confidence="high",
                source_agent="T06",
                severity="medium" if page.word_count > threshold["min_words"] * 0.5 else "high",
                impact_business="Medium",
                gain_potentiel="High" if page_type in ("article", "produit") else "Medium",
                effort="Variable — enrichir le contenu de la page",
                priority="P2",
                do_not_recommend_if=do_not,
            ))

    # 2. Duplication detection
    pages_with_content = [(p, _get_visible_text(p)) for p in state.crawled_pages
                          if p.status_code == 200 and not p.fetch_error and _get_visible_text(p).strip()]

    # Exact duplicates (MD5)
    hashes = Counter()
    page_hashes = {}
    for page, text in pages_with_content:
        h = _text_hash(text)
        hashes[h] += 1
        page_hashes[page.url] = h

    for h, count in hashes.items():
        if count > 1:
            dup_urls = [url for url, ph in page_hashes.items() if ph == h]
            dup_pairs.append({"urls": dup_urls, "similarity": 1.0, "type": "exact", "confidence": "high"})

    # Near-duplicates (cosinus > 0.85)
    if len(pages_with_content) > 1 and len(pages_with_content) < 100:
        for i in range(len(pages_with_content)):
            for j in range(i + 1, len(pages_with_content)):
                pi, ti = pages_with_content[i]
                pj, tj = pages_with_content[j]

                # Skip si deja detectes comme exact duplicates
                if page_hashes.get(pi.url) == page_hashes.get(pj.url):
                    continue

                sim = _cosine_similarity(ti, tj)
                if sim > 0.85:
                    confidence = "high" if sim > 0.90 else "medium"
                    dup_pairs.append({
                        "urls": [pi.url, pj.url],
                        "similarity": round(sim, 3),
                        "type": "near-duplicate",
                        "confidence": confidence,
                    })

    # Limiter les paires de duplicats
    if len(dup_pairs) > 20:
        dup_pairs.sort(key=lambda x: -x["similarity"])
        dup_pairs = dup_pairs[:20]

    state.duplicates = dup_pairs

    # Generer les issues de duplication
    for pair in dup_pairs[:10]:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="content",
            description=f"Contenu duplique ({pair['type']}, similarite {pair['similarity']:.0%}) entre {len(pair['urls'])} pages",
            url=pair["urls"][0],
            observed=f"duplication: {pair['type']}, sim={pair['similarity']}",
            rule=f"similarite {'> 0.85' if pair['type'] == 'near-duplicate' else 'exacte = 1.0'}",
            confidence=pair["confidence"],
            source_agent="T06",
            severity="high" if pair["similarity"] > 0.90 else "medium",
            impact_business="High",
            gain_potentiel="High",
            effort="Consolider les pages dupliquees ou les differencier",
            priority="P2" if pair["similarity"] > 0.90 else "P3",
        ))

    logger.info(f"T06: {thin_count} thin content pages, {len(dup_pairs)} duplicate pairs")

    # Scoring
    if state.crawled_pages:
        total = max(1, len(state.crawled_pages))
        non_thin = total - thin_count
        dup_penalty = min(30, len(dup_pairs) * 5)
        score = int((non_thin / total) * 70) + max(0, 30 - dup_penalty)
        state.scores.content.score = min(100, score)
        state.scores.content.confidence = "high"

    state.updated_at = datetime.now()
    return state
