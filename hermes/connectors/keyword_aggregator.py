"""Aggregateur de donnees mots-cles — multi-source avec fallback.

Priorite :
1. DataForSEO (volume absolu, CPC, competition) — deja configure
2. Keywords Everywhere (volume + trend) — si credits dispo
3. pytrends (trend relatif) — gratuit, fallback zero-cost
4. RankParse (DA domaines) — pour faisabilite SEO

Objectif : toujours retourner les meilleures donnees disponibles,
quel que soit l'etat des credits des differentes APIs.
"""

import logging
from typing import Any, Optional

from hermes.connectors.dataforseo_connector import dataforseo
from hermes.connectors.keywordseverywhere_connector import keywordseverywhere
from hermes.connectors.rankparse_connector import rankparse

logger = logging.getLogger("hermes.keyword_aggregator")


async def get_keyword_data(keyword: str, country: str = "fr") -> dict:
    """Recupere les meilleures donnees mot-cle disponibles.

    Aggregate les resultats de DataForSEO → KE → pytrends (fallback).
    Retourne toujours un dict, meme si partiel.

    Returns: {search_volume, cpc, competition, trend, source}
    """
    result = {
        "search_volume": 0,
        "cpc": 0.0,
        "competition": 0.0,
        "competition_label": "",
        "trend_direction": None,
        "trend_data": [],
        "source": "none",
        "sources_used": [],
    }

    # 1. DataForSEO — meilleure source (volume absolu, pay-as-you-go)
    if dataforseo.is_configured:
        try:
            related = await dataforseo.get_related_keywords(keyword, country, limit=5)
            if related:
                # Le mot-cle lui-meme n'est pas directement dans related_keywords,
                # mais le premier resultat est generalement le plus proche
                main = related[0]
                result["search_volume"] = main.get("search_volume", 0)
                result["cpc"] = main.get("cpc", 0)
                result["competition"] = main.get("competition_index", main.get("competition", 0)) / 100
                if result["competition"] <= 0.33:
                    result["competition_label"] = "Faible"
                elif result["competition"] <= 0.66:
                    result["competition_label"] = "Moyenne"
                else:
                    result["competition_label"] = "Elevee"
                result["source"] = "dataforseo"
                result["sources_used"].append("dataforseo")
                logger.info(f"Keyword data from DataForSEO: vol={result['search_volume']}, cpc={result['cpc']}")
                return result
        except Exception as e:
            logger.warning(f"DataForSEO keyword data failed: {e}")

    # 2. Keywords Everywhere — si credits
    if keywordseverywhere.is_configured:
        try:
            ke_data = await keywordseverywhere.get_keyword_metrics([keyword], country)
            if ke_data and keyword.lower() in ke_data:
                metrics = ke_data[keyword.lower()]
                result["search_volume"] = metrics.get("vol", 0)
                result["cpc"] = metrics.get("cpc", 0)
                result["competition"] = metrics.get("competition", 0)
                result["competition_label"] = keywordseverywhere.comp_label(result["competition"])
                trend = metrics.get("trend", [])
                if trend:
                    result["trend_data"] = trend
                    result["trend_direction"] = keywordseverywhere.trend_direction(trend)
                if not result["source"] or result["source"] == "none":
                    result["source"] = "keywordseverywhere"
                result["sources_used"].append("keywordseverywhere")
                logger.info(f"Keyword data from KE: vol={result['search_volume']}")
                return result
        except Exception as e:
            logger.warning(f"KE keyword data failed: {e}")

    # 3. pytrends — fallback gratuit (trend relatif uniquement, pas de volume)
    try:
        from pytrends.request import TrendReq
        pytrends = TrendReq(hl="fr-FR", tz=60, timeout=10)
        pytrends.build_payload(kw_list=[keyword], timeframe="today 12-m")
        trend_df = pytrends.interest_over_time()
        if not trend_df.empty and keyword in trend_df.columns:
            values = trend_df[keyword].dropna().tolist()
            if values:
                # Normalise 0-100 → estimation grossiere de volume
                avg_interest = sum(values) / len(values)
                # 0-100 → 0-10000 (estimation tres approximative)
                estimated_vol = int(avg_interest * 100)
                result["search_volume"] = estimated_vol
                result["trend_data"] = values
                recent = sum(values[-3:]) / 3 if len(values) >= 3 else 0
                prev = sum(values[-6:-3]) / 3 if len(values) >= 6 else 0
                if prev > 0:
                    result["trend_direction"] = round(((recent - prev) / prev) * 100)
                if not result["source"] or result["source"] == "none":
                    result["source"] = "pytrends"
                result["sources_used"].append("pytrends")
                logger.info(f"Keyword trend from pytrends: avg_interest={avg_interest:.0f}")
    except ImportError:
        logger.info("pytrends not installed — skipping free trend fallback")
    except Exception as e:
        logger.warning(f"pytrends fallback failed: {e}")

    return result


async def get_domain_authority_batch(domains: list[str]) -> dict[str, dict]:
    """Recupere le DA pour une liste de domaines via RankParse.

    Si RankParse n'est pas configure, retourne un dict vide.
    """
    if not rankparse.is_configured or not domains:
        return {}

    try:
        return await rankparse.batch_domain_authority(domains[:50])
    except Exception as e:
        logger.warning(f"RankParse batch DA failed: {e}")
        return {}


async def enrich_serp_with_da(serp_top10: list[dict]) -> list[dict]:
    """Enrichit les resultats SERP avec le Domain Authority.

    Args:
        serp_top10: [{"domain": "amazon.fr", ...}, ...]

    Returns: meme liste avec "da" ajoute a chaque entree
    """
    if not rankparse.is_configured:
        return serp_top10

    domains = list(set(r.get("domain", "") for r in serp_top10[:10] if r.get("domain")))
    if not domains:
        return serp_top10

    try:
        das = await rankparse.batch_domain_authority(domains)
        for result in serp_top10:
            domain = result.get("domain", "")
            if domain in das:
                result["da"] = das[domain].get("da", 0)
                result["backlinks"] = das[domain].get("backlinks", 0)
                result["referring_domains"] = das[domain].get("referring_domains", 0)
        logger.info(f"Enriched {len(das)} domains with DA from RankParse")
    except Exception as e:
        logger.warning(f"RankParse DA enrichment failed: {e}")

    return serp_top10
