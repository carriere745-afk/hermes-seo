"""S01 — Rank Tracker.

Collecte les positions actuelles pour chaque mot-cle depuis :
1. GSC API (source principale, gratuite)
2. DataForSEO (mots-cles < 10 impressions GSC, temps reel)
3. Keywords Everywhere (volume de recherche)

Stocke dans SQLite (positions_history) pour constituer l'historique.
Non skippable — agent fondateur du pipeline.

$0 avec GSC, ~$0.001/kw avec DataForSEO.
"""

import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse

from hermes.models.serp_visibility import SerpVisibilityState, PositionEntry

logger = logging.getLogger("hermes.serp.sv01")


async def _fetch_gsc_positions(state: SerpVisibilityState) -> list[dict]:
    """Recupere les positions depuis GSC pour tous les mots-cles du site."""
    results = []
    try:
        from hermes.connectors.gsc_connector import gsc
        if not gsc.is_configured:
            return results

        domain = state.domain
        site_url_gsc = f"sc-domain:{domain}"

        # Recuperer les donnees sur 7, 28 et 90 jours
        for days in (7, 28, 90):
            data = await gsc.query(
                site_url_gsc,
                start_date=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"),
                end_date=datetime.now().strftime("%Y-%m-%d"),
                dimensions=["query", "page"],
                row_limit=500,
            )
            if data:
                for row in data:
                    keyword = row.get("query", "").strip()
                    if not keyword:
                        continue
                    # Si mots-cles definis, filtrer
                    if state.keywords and keyword.lower() not in [k.lower() for k in state.keywords]:
                        continue
                    results.append({
                        "keyword": keyword,
                        "url": row.get("page", ""),
                        "clicks": int(row.get("clicks", 0) or 0),
                        "impressions": int(row.get("impressions", 0) or 0),
                        "ctr": round(float(row.get("ctr", 0) or 0) * 100, 2),
                        "position": round(float(row.get("position", 0) or 0), 1),
                        "source": "GSC",
                        "device": "all",
                    })

        logger.info(f"S01: GSC returned {len(results)} rows")
    except Exception as e:
        logger.warning(f"S01: GSC fetch failed ({e})")

    return results


async def _enrich_with_volume(keywords: list[str]) -> dict[str, int]:
    """Enrichit avec les volumes de recherche (Keywords Everywhere)."""
    volumes = {}
    try:
        from hermes.connectors.keywordseverywhere_connector import keywordseverywhere
        if not keywordseverywhere.is_configured:
            return volumes

        # Batch par 20
        for i in range(0, len(keywords), 20):
            batch = keywords[i:i + 20]
            data = await keywordseverywhere.get_keyword_metrics(batch, "fr")
            for kw, metrics in data.items():
                volumes[kw] = metrics.get("vol", 0)
    except Exception as e:
        logger.debug(f"S01: KE volume fetch skipped ({e})")
    return volumes


async def _enrich_dataforseo(keywords: list[str], state: SerpVisibilityState) -> list[dict]:
    """Complete avec DataForSEO pour les mots-cles a faible volume GSC."""
    results = []
    # Limite : on n'appelle DataForSEO que si GSC a peu de donnees pour ces mots-cles
    # Pour le Sprint 1, on skip (deja couteux)
    return results


async def run(state: SerpVisibilityState) -> SerpVisibilityState:
    state.current_agent = "sv01"

    # 1. Si pas de mots-cles definis, recuperer depuis GSC
    if not state.keywords:
        try:
            from hermes.connectors.gsc_connector import gsc
            if gsc.is_configured:
                domain = state.domain
                site_url = f"sc-domain:{domain}"
                data = await gsc.query(
                    site_url,
                    start_date=(datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d"),
                    end_date=datetime.now().strftime("%Y-%m-%d"),
                    dimensions=["query"],
                    row_limit=200,
                )
                if data:
                    keywords = list(set(row.get("query", "").strip() for row in data if row.get("query")))
                    state.keywords = keywords[:200]
                    logger.info(f"S01: {len(state.keywords)} keywords auto-detected from GSC")
        except Exception as e:
            logger.warning(f"S01: auto-detect keywords failed ({e})")

    if not state.keywords:
        logger.warning("S01: aucun mot-cle — skip")
        state.status = "no_keywords"
        return state

    # 2. Collecte GSC
    gsc_data = await _fetch_gsc_positions(state)

    # 3. Enrichir volumes KE
    unique_kw = list(set(r["keyword"] for r in gsc_data))[:100]
    volumes = await _enrich_with_volume(unique_kw)

    # 4. Transformer en PositionEntry et stocker SQLite
    today = datetime.now().isoformat()
    entries = []

    for row in gsc_data:
        kw = row["keyword"]
        entry = {
            "url": row["url"],
            "keyword": kw,
            "position": int(row["position"]),
            "impressions": row["impressions"],
            "clicks": row["clicks"],
            "ctr": row["ctr"],
            "search_volume": volumes.get(kw, 0),
            "device": row.get("device", "all"),
            "source": row["source"],
            "date": today,
            "variation": 0,
            "position_previous": 0,
        }
        entries.append(entry)

        state.positions.append(PositionEntry(**entry))

    # Stocker dans SQLite
    if entries:
        try:
            from hermes.core.serp_db import insert_positions_batch
            count = insert_positions_batch(entries)
            logger.info(f"S01: {count} positions stored in SQLite")
        except Exception as e:
            logger.warning(f"S01: SQLite store failed ({e})")

    logger.info(f"S01: {len(state.positions)} positions tracked for {len(state.keywords)} keywords")
    state.status = "collected"
    state.updated_at = datetime.now()
    return state
