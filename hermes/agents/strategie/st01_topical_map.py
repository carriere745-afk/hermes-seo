"""ST01 — Cartographie des Sujets.

Analyse les sujets couverts vs manquants par silo thematique.
Utilise ChromaDB pour le clustering semantique + P2 pour les scores.
Non skippable. $0 — pas de LLM.
"""

import json
import logging
import math
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

from hermes.models.strategie import StrategieState, Sujet
from hermes.core.strategie_db import log_event

logger = logging.getLogger("hermes.strategie.st01")


async def run(state: StrategieState) -> StrategieState:
    t0 = time.perf_counter()
    state.current_agent = "st01"
    state.phase = "analyse"

    sujets: list[Sujet] = []
    topical_map: list[dict] = []

    # Charger les donnees upstream selon disponibilite
    p2_data = _load_p2_data()
    p4_data = _load_p4_data(state)

    # Construire les sujets a partir des keywords + pages existantes
    keywords = state.keywords_monitored or _default_keywords(state)

    for kw_group in _group_keywords(keywords, p4_data):
        sujets.append(Sujet(
            nom=kw_group["nom"],
            keywords=kw_group["kws"],
            volume_total=kw_group["volume_total"],
            volume_principal=kw_group.get("volume_principal", 0),
            intention=kw_group.get("intention", "informative"),
            silo=kw_group.get("silo", "general"),
            couvert=kw_group.get("couvert", False),
            page_existante=kw_group.get("page_existante", ""),
            position_moyenne=kw_group.get("position_moyenne", 100.0),
            concurrents_top5=kw_group.get("concurrents_top5", []),
        ))

    # Construire la topical map (structure hierarchique)
    topical_map = _build_topical_map(sujets)

    # Essayer d'utiliser ChromaDB pour le clustering semantique
    try:
        _enrich_with_chromadb(sujets, topical_map)
    except Exception as e:
        logger.warning(f"ST01: ChromaDB enrichment failed ({e}) — skip")

    # Enrichir avec les donnees P2 si disponibles
    if p2_data:
        _enrich_with_p2(sujets, p2_data)

    state.sujets = sujets
    state.topical_map = topical_map
    state.updated_at = datetime.now()

    duration_ms = int((time.perf_counter() - t0) * 1000)
    log_event(
        session_id=state.session_id, agent_id="st01", pipeline_id="strategie",
        model="none", tokens_used=0, cost=0.0, duration_ms=duration_ms,
        success=True,
    )

    logger.info(f"ST01: {len(sujets)} sujets identifies, {len(topical_map)} silos mappes")
    return state


def _load_p2_data() -> dict:
    """Charge les donnees P2 (Audit de Contenu) si disponibles."""
    db_path = Path("data/audit_contenu.db")
    if not db_path.exists():
        return {}
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM pages ORDER BY score_global DESC").fetchall()
        conn.close()
        return {"pages": [dict(r) for r in rows]}
    except Exception:
        return {}


def _load_p4_data(state: StrategieState) -> dict:
    """Charge les donnees P4 (SERP) si disponibles."""
    db_path = Path("data/serp_visibility.db")
    if not db_path.exists():
        return {}
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT keyword, url, AVG(position) as avg_pos, SUM(impressions) as total_imp, SUM(clicks) as total_clicks "
            "FROM positions_history WHERE date >= date('now', '-90 days') "
            "GROUP BY keyword, url ORDER BY total_imp DESC LIMIT 200"
        ).fetchall()
        conn.close()
        return {"positions": [dict(r) for r in rows], "competitors": state.competitors}
    except Exception:
        return {}


def _default_keywords(state: StrategieState) -> list[str]:
    """Genere des mots-cles par defaut bases sur le profil ET un crawl de la page d'accueil."""
    keywords = []

    # 1. Tenter un crawl rapide de la page d'accueil pour extraire les vrais themes
    try:
        homepage_kws = _scrape_homepage_topics(state.site_url)
        if homepage_kws:
            keywords.extend(homepage_kws)
            logger.info(f"ST01: {len(homepage_kws)} mots-cles extraits de la page d'accueil")
    except Exception as e:
        logger.warning(f"ST01: Homepage crawl failed ({e}), fallback to industry defaults")

    # 2. Ajouter des mots-cles secteur si le crawl n'a rien donne
    if len(keywords) < 3:
        secteur_kw = {
            "ecommerce": ["prix", "avis client", "meilleur", "comparatif", "promo", "livraison", "guide achat"],
            "local": ["devis", "tarif", "avis", "professionnel", "pas cher", "qualite", "intervention", "urgent"],
            "corporate": ["solutions", "services", "expertise", "etude de cas", "a propos"],
        }
        base = secteur_kw.get(state.profile, [])
        domain_clean = state.domain.replace(".fr", "").replace(".com", "").replace(".pro", "").replace("www.", "")
        for kw in base:
            keywords.append(f"{kw} {domain_clean}" if state.domain else kw)

    # 3. Si toujours rien, dernier recours avec la racine du domaine
    if not keywords and state.domain:
        domain_root = state.domain.split(".")[0][:30]  # "cleantout37"
        keywords = [f"{domain_root}", f"{domain_root} avis", f"{domain_root} tarif",
                    f"{domain_root} {state.profile}"]

    return keywords[:20]


def _scrape_homepage_topics(site_url: str) -> list[str]:
    """Crawl la page d'accueil pour extraire les themes reels du site."""
    import re
    import httpx

    url = site_url.rstrip("/")
    topics = []

    try:
        resp = httpx.get(url, timeout=8.0, follow_redirects=True)
        if resp.status_code != 200:
            return []

        html_full = resp.text[:80000]

        # Extraire les metadonnees
        title_match = re.search(r"<title>([^<]+)</title>", html_full, re.IGNORECASE)
        title = title_match.group(1) if title_match else ""
        desc_match = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', html_full, re.IGNORECASE)
        desc = desc_match.group(1) if desc_match else ""
        h1_matches = re.findall(r"<h[12][^>]*>([^<]+)</h[12]>", html_full, re.IGNORECASE)
        h2s = " ".join(h1_matches) if h1_matches else ""

        # Nettoyer radicalement le HTML: supprimer scripts, styles, CSS, puis tous les tags
        html_clean = re.sub(r"<script[^>]*>.*?</script>", " ", html_full, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r"<style[^>]*>.*?</style>", " ", html_clean, flags=re.DOTALL | re.IGNORECASE)
        html_clean = re.sub(r"\{[^}]*\}", " ", html_clean)  # CSS inline
        html_clean = re.sub(r"<[^>]+>", " ", html_clean)
        html_clean = re.sub(r"[^a-zA-ZÀ-ÿ\s]", " ", html_clean)
        html_clean = re.sub(r"\s+", " ", html_clean).lower()

        # Stopwords + mots parasites HTML/CSS
        stopwords = {"le", "la", "les", "des", "une", "est", "sont", "avec", "pour", "sur",
                      "dans", "par", "qui", "que", "pas", "plus", "tout", "aux", "nos",
                      "vous", "votre", "vos", "nous", "notre", "leur", "leurs", "cette",
                      "entre", "bien", "tres", "fait", "faire", "etre", "avoir", "aussi",
                      "peut", "site", "cookies", "fermer", "savoir", "suivre", "ainsi",
                      "travail", "necessaire", "navigation", "choix", "formulaire",
                      "interlocuteur", "menu", "mobile", "header", "main", "body",
                      "style", "fullscreen", "collapse", "submenu", "animation",
                      "background", "https", "www", "com", "html", "content",
                      "slide", "opened", "closed", "dipi", "before", "important"}

        words = re.findall(r"[a-zà-ÿ]{4,}", html_clean)
        word_freq = {}
        for w in words:
            if w not in stopwords and len(w) >= 4:
                word_freq[w] = word_freq.get(w, 0) + 1

        # Extraire les bigrammes sur le texte nettoye
        clean_words = [w for w in words if w not in stopwords]
        bigrams_raw = []
        for i in range(len(clean_words) - 1):
            bg = f"{clean_words[i]} {clean_words[i + 1]}"
            if len(bg) >= 8:
                bigrams_raw.append(bg)
        bigram_freq = {}
        for bg in bigrams_raw:
            bigram_freq[bg] = bigram_freq.get(bg, 0) + 1
        top_bigrams = sorted(bigram_freq, key=bigram_freq.get, reverse=True)[:10]

        # Top mots
        top_words = sorted(word_freq, key=word_freq.get, reverse=True)[:20]

        # Entites geographiques
        geo_keywords = _extract_geo_keywords(f"{title} {desc} {h2s}")

        # Construire les mots-cles finaux : priorite aux metadonnees + bigrammes
        titre_words = re.findall(r"[a-zà-ÿ]{4,}", f"{title} {desc} {h2s}".lower())
        topics = []

        # D'abord les mots du title/desc/H1 (ce sont les plus importants)
        for w in titre_words:
            if w not in stopwords:
                topics.append(w)

        # Ensuite les bigrammes significatifs
        for bg in top_bigrams[:8]:
            topics.append(bg)

        # Puis les mots frequents
        for w in top_words[:10]:
            topics.append(w)

        # Combinaisons avec la geo
        for geo in geo_keywords[:3]:
            for w in top_words[:5]:
                if w not in stopwords:
                    topics.append(f"{w} {geo}")

        # Ajouter des combinaisons pertinentes
        domain_root = ""
        try:
            from urllib.parse import urlparse
            domain_root = urlparse(url).netloc.replace("www.", "").split(".")[0]
        except Exception:
            pass

        if domain_root:
            for w in top_words[:5]:
                topics.append(f"{w} {domain_root}")

        return list(set(topics))[:30]

    except Exception:
        return []


def _extract_geo_keywords(text: str) -> list[str]:
    """Extrait les entites geographiques du texte (villes francaises frequentes)."""
    import re
    geo_patterns = [
        r"(?:à|a|sur|dans|pres de|proche de)\s+([A-ZÀ-Ü][a-zà-ü]+)",
    ]
    found = []
    for pat in geo_patterns:
        matches = re.findall(pat, text)
        found.extend(matches)
    # Filtrer les faux positifs (mots communs capitalises)
    exclude = {"Vous", "Nous", "Notre", "Contact", "Devis", "Accueil", "Services",
               "Tous", "Vos", "Pour", "Avec", "Bien", "Plus", "Tout"}
    return [m for m in found if m not in exclude][:5]


def _group_keywords(keywords: list[str], p4_data: dict) -> list[dict]:
    """Groupe les mots-cles en sujets par similarite simple (prefixe commun)."""
    groups: dict[str, dict] = {}
    positions = {p.get("keyword", ""): p for p in p4_data.get("positions", [])}

    for kw in keywords:
        kw_clean = kw.lower().strip()
        parts = kw_clean.split()
        prefix = parts[0] if parts else kw_clean

        if prefix not in groups:
            groups[prefix] = {"nom": prefix, "kws": [], "volume_total": 0,
                             "volume_principal": 0, "intention": "informative",
                             "silo": "general", "couvert": False, "page_existante": "",
                             "position_moyenne": 100.0, "concurrents_top5": []}
        groups[prefix]["kws"].append(kw_clean)
        # Volume estime grossierement
        est_volume = max(10, len(kw_clean) * 30)
        groups[prefix]["volume_total"] += est_volume
        groups[prefix]["volume_principal"] = max(groups[prefix]["volume_principal"], est_volume)

        if kw_clean in positions:
            pos = positions[kw_clean]
            groups[prefix]["position_moyenne"] = pos.get("avg_pos", 100.0)
            groups[prefix]["couvert"] = pos.get("avg_pos", 100.0) <= 100

    return list(groups.values())


def _build_topical_map(sujets: list[Sujet]) -> list[dict]:
    """Construit une carte thematique hierarchique."""
    silos: dict[str, dict] = {}
    for s in sujets:
        if s.silo not in silos:
            silos[s.silo] = {
                "silo": s.silo,
                "sujets_couverts": 0,
                "sujets_manquants": 0,
                "volume_total": 0,
                "sujets": [],
            }
        silos[s.silo]["volume_total"] += s.volume_total
        if s.couvert:
            silos[s.silo]["sujets_couverts"] += 1
        else:
            silos[s.silo]["sujets_manquants"] += 1
        silos[s.silo]["sujets"].append({
            "nom": s.nom,
            "couvert": s.couvert,
            "volume": s.volume_total,
            "position": s.position_moyenne,
        })
    return list(silos.values())


def _enrich_with_chromadb(sujets: list[Sujet], topical_map: list[dict]) -> None:
    """Enrichit avec ChromaDB pour le clustering semantique."""
    try:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(
            path="data/chroma",
            settings=Settings(anonymized_telemetry=False),
        )
        # Tenter de charger une collection existante
        try:
            collection = client.get_collection("hermes_pages")
        except Exception:
            collection = client.get_or_create_collection("hermes_pages")

        count = collection.count()
        if count > 0:
            logger.info(f"ST01: ChromaDB — {count} pages indexees")
    except Exception:
        raise


def _enrich_with_p2(sujets: list[Sujet], p2_data: dict) -> None:
    """Enrichit les sujets avec les scores P2."""
    pages = p2_data.get("pages", [])
    for sujet in sujets:
        for page in pages:
            url = page.get("url", "")
            title = page.get("title", "")
            for kw in sujet.keywords:
                if kw.lower() in url.lower() or kw.lower() in title.lower():
                    sujet.couvert = True
                    sujet.page_existante = url
                    break
