"""Connecteur Bing Webmaster API — fallback gratuit pour P4/P6.

API Key gratuite via Bing Webmaster Tools.
Fournit : backlinks, positions, mots-cles, indexation.
Utilise comme fallback quand GSC et DataForSEO sont indisponibles.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Optional

import httpx

from hermes import config

logger = logging.getLogger("hermes.bing")


class BingWebmasterConnector:
    """Client Bing Webmaster API (gratuit, fallback)."""

    BASE_URL = "https://ssl.bing.com/webmaster/api.svc/json"

    def __init__(self):
        self._api_key = ""
        try:
            self._api_key = str(config._cfg._resolve("BING_WEBMASTER_API_KEY"))
        except Exception:
            pass

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _headers(self) -> dict:
        return {"Content-Type": "application/json"}

    def _auth_params(self) -> dict:
        return {"apikey": self._api_key}

    async def query(self, endpoint: str, params: dict | None = None) -> dict:
        if not self.is_configured:
            raise ValueError("Bing Webmaster API non configuree. Ajoutez BING_WEBMASTER_API_KEY dans .env")

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/{endpoint.lstrip('/')}",
                    headers=self._headers(),
                    params={**self._auth_params(), **(params or {})},
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.warning("Bing Webmaster: API key invalide ou expiree")
                raise ValueError("Bing Webmaster API key invalide. Verifiez BING_WEBMASTER_API_KEY.")
            raise
        except Exception as e:
            logger.warning(f"Bing Webmaster query failed: {e}")
            raise

    async def get_backlinks(self, site_url: str) -> list[dict]:
        """Recupere les backlinks connus par Bing pour un site."""
        try:
            data = await self.query(
                "GetBacklinks",
                {"siteUrl": site_url},
            )
            links = []
            for item in data.get("d", {}).get("results", []):
                links.append({
                    "source_url": item.get("Url", ""),
                    "source_domain": item.get("SourceDomain", ""),
                    "target_url": item.get("TargetUrl", ""),
                    "anchor_text": item.get("AnchorText", ""),
                })
            logger.info(f"Bing: {len(links)} backlinks trouves pour {site_url}")
            return links
        except Exception as e:
            logger.warning(f"Bing backlinks failed: {e}")
            return []

    async def get_keyword_stats(self, site_url: str) -> list[dict]:
        """Recupere les mots-cles pour lesquels le site est positionne."""
        try:
            data = await self.query(
                "GetKeywordStats",
                {"siteUrl": site_url},
            )
            keywords = []
            for item in data.get("d", {}).get("results", []):
                keywords.append({
                    "keyword": item.get("Query", ""),
                    "impressions": item.get("Impressions", 0),
                    "clicks": item.get("Clicks", 0),
                    "position": item.get("Position", 0),
                    "ctr": item.get("CTR", 0),
                })
            logger.info(f"Bing: {len(keywords)} mots-cles trouves pour {site_url}")
            return keywords
        except Exception as e:
            logger.warning(f"Bing keyword stats failed: {e}")
            return []

    async def get_domain_metrics(self, site_url: str) -> dict:
        """Metriques globales du domaine."""
        return {
            "source": "bing",
            "backlinks": len(await self.get_backlinks(site_url)),
            "keywords": len(await self.get_keyword_stats(site_url)),
        }


bing = BingWebmasterConnector()
