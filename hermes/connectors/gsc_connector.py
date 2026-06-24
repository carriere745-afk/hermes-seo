"""Connecteur Google Search Console — Agent 26.

Utilise l'API Google Search Console pour recuperer les donnees
de performance post-publication : clics, impressions, CTR, position.

OAuth 2.0 flow gere via refresh token (pas d'interaction utilisateur).
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx

from hermes import config

logger = logging.getLogger("hermes.gsc")


class GSCConnector:
    """Client Google Search Console avec OAuth 2.0 refresh token."""

    BASE_URL = "https://www.googleapis.com/webmasters/v3"
    TOKEN_URL = "https://oauth2.googleapis.com/token"

    def __init__(self):
        self._client_id = str(config.GSC_CLIENT_ID) if hasattr(config, 'GSC_CLIENT_ID') else ""
        self._client_secret = str(config.GSC_CLIENT_SECRET) if hasattr(config, 'GSC_CLIENT_SECRET') else ""
        self._refresh_token = self._get_env("GSC_REFRESH_TOKEN")
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._client_secret and self._refresh_token)

    def _get_env(self, key: str) -> str:
        try:
            val = config._cfg._resolve(key)
            return val
        except Exception:
            return ""

    async def _ensure_token(self) -> None:
        """Rafraichit le token OAuth si necessaire."""
        if self._access_token and self._token_expiry and datetime.now() < self._token_expiry:
            return

        if not self.is_configured:
            raise ValueError(
                "GSC non configure. Definissez GSC_CLIENT_ID, GSC_CLIENT_SECRET "
                "et GSC_REFRESH_TOKEN dans .env ou Streamlit Secrets."
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expiry = datetime.now() + timedelta(seconds=data.get("expires_in", 3600))

    async def query(
        self,
        site_url: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        dimensions: Optional[list[str]] = None,
        row_limit: int = 100,
    ) -> list[dict]:
        """Interroge l'API Search Console pour un site.

        Args:
            site_url: URL du site dans GSC (ex: 'https://www.example.com')
            start_date: date debut (YYYY-MM-DD), defaut 30 jours
            end_date: date fin (YYYY-MM-DD), defaut aujourd'hui
            dimensions: ['query', 'page', 'country', 'device']
            row_limit: nombre max de lignes

        Returns: liste de {clicks, impressions, ctr, position, query, page}
        """
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not dimensions:
            dimensions = ["query", "page"]

        await self._ensure_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/sites/{site_url}/searchAnalytics/query",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": dimensions,
                    "rowLimit": min(row_limit, 25000),
                },
            )
            if resp.status_code == 403:
                logger.warning(
                    f"GSC 403: Le site '{site_url}' n'est pas verifie dans Google Search Console "
                    f"pour le compte OAuth actuel."
                )
                raise ValueError(
                    f"Site non verifie dans GSC: '{site_url}'. "
                    f"Ouvrez https://search.google.com/search-console et ajoutez cette propriete."
                )
            resp.raise_for_status()
            data = resp.json()

            rows = data.get("rows", [])
            result = []
            for row in rows:
                entry = {
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": round(row.get("ctr", 0) * 100, 2),  # 0-1 → 0-100%
                    "position": round(row.get("position", 0), 1),
                }
                for i, dim in enumerate(dimensions):
                    entry[dim] = row["keys"][i]
                result.append(entry)

            logger.info(
                f"GSC query OK: {len(result)} rows pour {site_url} "
                f"({start_date} → {end_date})"
            )
            return result

    async def get_url_performance(
        self, site_url: str, page_url: str, days: int = 30
    ) -> dict:
        """Recupere les performances GSC pour une URL specifique.

        Returns: {clicks, impressions, ctr, position_moyenne, top_queries}
        """
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        end_date = datetime.now().strftime("%Y-%m-%d")

        await self._ensure_token()

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Query avec filtre page
            resp = await client.post(
                f"{self.BASE_URL}/sites/{site_url}/searchAnalytics/query",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "startDate": start_date,
                    "endDate": end_date,
                    "dimensions": ["query"],
                    "dimensionFilterGroups": [{
                        "filters": [{
                            "dimension": "page",
                            "operator": "equals",
                            "expression": page_url,
                        }]
                    }],
                    "rowLimit": 100,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        rows = data.get("rows", [])
        total_clicks = sum(r.get("clicks", 0) for r in rows)
        total_impressions = sum(r.get("impressions", 0) for r in rows)
        avg_ctr = (
            round(total_clicks / total_impressions * 100, 2)
            if total_impressions > 0 else 0
        )
        positions = [r.get("position", 0) for r in rows if r.get("position")]
        avg_position = round(sum(positions) / len(positions), 1) if positions else 0

        return {
            "page_url": page_url,
            "clicks": total_clicks,
            "impressions": total_impressions,
            "ctr": avg_ctr,
            "position_moyenne": avg_position,
            "top_queries": sorted(
                [{"query": r["keys"][0], "clicks": r.get("clicks", 0)}
                 for r in rows],
                key=lambda x: x["clicks"], reverse=True
            )[:20],
            "period_days": days,
            "date_start": start_date,
            "date_end": end_date,
        }

    async def list_sites(self) -> list[dict]:
        """Liste les sites accessibles via GSC."""
        await self._ensure_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.BASE_URL}/sites",
                headers={"Authorization": f"Bearer {self._access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {"site_url": s.get("siteUrl", ""),
                 "permission_level": s.get("permissionLevel", "")}
                for s in data.get("siteEntry", [])
            ]

    async def check_indexation(self, site_url: str, page_url: str) -> dict:
        """Verifie si une URL est indexee par Google."""
        await self._ensure_token()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.BASE_URL}/urlInspection/index:inspect",
                headers={
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "inspectionUrl": page_url,
                    "siteUrl": site_url,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            inspection = data.get("inspectionResult", {})
            index_status = inspection.get("indexStatusResult", {})
            return {
                "url": page_url,
                "indexed": index_status.get("coverageState") == "Indexed",
                "coverage_state": index_status.get("coverageState", "unknown"),
                "last_crawled": index_status.get("lastCrawlTime"),
                "crawled_as": index_status.get("crawledAs", ""),
                "robots_txt": index_status.get("robotsTxtState", ""),
                "sitemap": index_status.get("sitemap", []),
            }


# Singleton
gsc = GSCConnector()
