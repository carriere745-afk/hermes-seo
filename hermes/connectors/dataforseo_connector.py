"""Connecteur DataForSEO — keywords, domain metrics, SERP positions.

Porte depuis saas-seo/lib/dataforseo.js (6 fonctions) + fc-solutions/lib/dataforseo-serp.mjs (8 fonctions).
API v3 avec Basic Auth (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD).
"""

import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Optional

import httpx

from hermes import config

logger = logging.getLogger("hermes.dataforseo")


class DataForSEOConnector:
    """Client DataForSEO API v3.

    Auth : Basic (login:password), pas de OAuth.
    """

    BASE_URL = "https://api.dataforseo.com/v3"

    def __init__(self):
        self._login = self._get_env("DATAFORSEO_LOGIN")
        self._password = self._get_env("DATAFORSEO_PASSWORD")

    @property
    def is_configured(self) -> bool:
        return bool(self._login and self._password)

    def _get_env(self, key: str) -> str:
        try:
            return str(config._cfg._resolve(key))
        except Exception:
            return ""

    def _auth_header(self) -> str:
        credentials = base64.b64encode(
            f"{self._login}:{self._password}".encode()
        ).decode()
        return f"Basic {credentials}"

    async def _post(self, endpoint: str, payload: list[dict]) -> dict:
        """Appel POST generique a DataForSEO."""
        if not self.is_configured:
            raise ValueError("DataForSEO non configure. Verifiez DATAFORSEO_LOGIN/PASSWORD dans .env")

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/{endpoint.lstrip('/')}",
                headers={
                    "Authorization": self._auth_header(),
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("status_code") and data["status_code"] >= 40000:
                raise ValueError(f"DataForSEO error {data['status_code']}: {data.get('status_message', '')}")

            return data

    async def get_domain_metrics(self, domains: list[str]) -> dict[str, dict]:
        """Recupere les metriques de domaine (traffic, keywords, backlinks).

        Args:
            domains: liste de domaines (ex: ["example.com", "other.com"])

        Returns: {domain: {rank, traffic_etv, keywords_count, backlinks_count}}
        """
        try:
            payload = [{"target": d} for d in domains[:20]]
            resp = await self._post(
                "dataforseo_labs/google/domain_metrics_by_categories/live",
                payload,
            )
            result = {}
            for task in (resp.get("tasks") or []):
                for item in (task.get("result") or []):
                    domain = item.get("target", "")
                    items = item.get("items") or [{}]
                    metrics = items[0] if items else {}
                    result[domain] = {
                        "rank": metrics.get("rank", 0),
                        "traffic_etv": metrics.get("etv", 0),
                        "keywords_count": metrics.get("count", 0),
                        "backlinks_count": item.get("referring_domains", 0),
                    }
            return result
        except Exception as e:
            logger.warning(f"DataForSEO domain_metrics failed: {e}")
            return {}

    async def get_related_keywords(
        self, keyword: str, language: str = "fr", limit: int = 20
    ) -> list[dict]:
        """Recherche de mots-cles associes avec volume et difficulte.

        Returns: [{keyword, search_volume, cpc, competition, trend}]
        """
        try:
            payload = [{
                "keyword": keyword,
                "language_code": language,
                "location_code": 2250,  # France
                "limit": limit,
            }]
            resp = await self._post(
                "dataforseo_labs/google/related_keywords/live",
                payload,
            )
            keywords = []
            for task in resp.get("tasks", []):
                for r in task.get("result", [])[:limit]:
                    for item in r.get("items", []):
                        keywords.append({
                            "keyword": item.get("keyword", ""),
                            "search_volume": item.get("search_volume", 0),
                            "cpc": item.get("cpc", 0),
                            "competition": item.get("competition", 0),
                            "competition_index": item.get("competition_index", 0),
                        })
            return keywords
        except Exception as e:
            logger.warning(f"DataForSEO related_keywords failed: {e}")
            return []

    async def get_keyword_suggestions(
        self, keyword: str, language: str = "fr", limit: int = 20
    ) -> list[dict]:
        """Suggestions de mots-cles (autocomplete-like)."""
        try:
            payload = [{
                "keyword": keyword,
                "language_code": language,
                "location_code": 2250,
                "limit": limit,
            }]
            resp = await self._post(
                "dataforseo_labs/google/keyword_suggestions/live",
                payload,
            )
            keywords = []
            for task in resp.get("tasks", []):
                for r in task.get("result", []):
                    for item in r.get("items", []):
                        keywords.append({
                            "keyword": item.get("keyword", ""),
                            "search_volume": item.get("search_volume", 0),
                            "cpc": item.get("cpc", 0),
                        })
            return keywords
        except Exception as e:
            logger.warning(f"DataForSEO keyword_suggestions failed: {e}")
            return []

    async def get_serp_organic(
        self, keyword: str, language: str = "fr", location: str = "France", depth: int = 20
    ) -> list[dict]:
        """Recupere les resultats organiques Google.

        Returns: [{position, title, url, domain, snippet}]
        """
        try:
            payload = [{
                "keyword": keyword,
                "language_name": language,
                "location_name": location,
                "depth": depth,
            }]
            resp = await self._post(
                "serp/google/organic/live/regular",
                payload,
            )
            results = []
            for task in resp.get("tasks", []):
                for r in task.get("result", []):
                    for item in r.get("items", []):
                        if item.get("type") == "organic":
                            url = item.get("url", "")
                            domain = ""
                            try:
                                from urllib.parse import urlparse
                                domain = urlparse(url).netloc.replace("www.", "")
                            except Exception:
                                pass
                            results.append({
                                "position": item.get("rank_absolute", 0),
                                "title": item.get("title", ""),
                                "url": url,
                                "domain": domain,
                                "snippet": item.get("description", ""),
                            })
            return results[:depth]
        except Exception as e:
            logger.warning(f"DataForSEO serp_organic failed: {e}")
            return []

    async def check_keyword_position(
        self, keyword: str, domain: str, language: str = "fr", location: str = "France"
    ) -> Optional[dict]:
        """Verifie la position d'un domaine pour un mot-cle.

        Returns: {position, url} or None si pas dans le top 100
        """
        try:
            results = await self.get_serp_organic(keyword, language, location, depth=100)
            clean_domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
            for r in results:
                if clean_domain in r.get("domain", ""):
                    return {"position": r["position"], "url": r["url"]}
            return None
        except Exception as e:
            logger.warning(f"DataForSEO position_check failed: {e}")
            return None


# Singleton
dataforseo = DataForSEOConnector()
