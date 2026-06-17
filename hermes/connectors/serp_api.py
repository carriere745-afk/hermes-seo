"""Connecteur SERP API — TalorData, Scrape.do et Serpstack.

Trois fournisseurs supportes avec fallback automatique.
Priorite (juin 2026) : TalorData > Scrape.do > Serpstack.

Sources :
- https://dev.to/talordata_elowen/2026-serp-api-comparison
- https://scrape.do/blog/google-serp-api/
"""

from typing import Optional

import httpx

from hermes import config
from hermes.core.exceptions import SerpAPIError


class SerpAPIClient:
    """Client unifie pour les APIs SERP.

    Priorite : TalorData ($0.25-0.90/1K, gratuit 1000 req/mois)
            > Scrape.do ($1.16/1K, 60% AI Overview)
            > Serpstack (fallback historique)
    """

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run

    async def search(
        self, keyword: str, location: str = "fr", language: str = "fr"
    ) -> dict:
        """Recupere les donnees SERP pour un mot-cle."""
        if self.dry_run:
            return self._mock_response(keyword)

        # Essayer TalorData en premier (le moins cher, le plus complet)
        if config.TALORDATA_API_KEY:
            try:
                return await self._search_talordata(keyword, location, language)
            except SerpAPIError:
                pass  # Fallback

        # Essayer Scrape.do
        if config.SCRAPEDO_API_KEY:
            try:
                return await self._search_scrapedo(keyword, location, language)
            except SerpAPIError:
                pass  # Fallback

        # Fallback Serpstack
        if config.SERPSTACK_API_KEY:
            return await self._search_serpstack(keyword, location, language)

        raise SerpAPIError(
            "Aucune API SERP configuree. Definissez TALORDATA_API_KEY, "
            "SCRAPEDO_API_KEY ou SERPSTACK_API_KEY dans .env, "
            "ou utilisez --dry-run."
        )

    async def _search_talordata(
        self, keyword: str, location: str, language: str
    ) -> dict:
        """Appelle l'API TalorData — compatible SerpApi, multi-engine."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.talordata.com/v1/serp",
                headers={
                    "Authorization": f"Bearer {config.TALORDATA_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "q": keyword,
                    "engine": "google",
                    "hl": language,
                    "gl": location,
                    "num": 10,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise SerpAPIError(f"TalorData error: {data['error']}")
            return data

    async def _search_scrapedo(
        self, keyword: str, location: str, language: str
    ) -> dict:
        """Appelle l'API Scrape.do — bon rapport qualite/prix, 60% AI Overview."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "https://api.scrape.do/v1/serp",
                params={
                    "api_key": config.SCRAPEDO_API_KEY,
                    "q": keyword,
                    "location": location,
                    "language": language,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise SerpAPIError(f"Scrape.do error: {data['error']}")
            return data

    async def _search_serpstack(
        self, keyword: str, location: str, language: str
    ) -> dict:
        """Appelle l'API Serpstack — fallback historique."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                "http://api.serpstack.com/search",
                params={
                    "access_key": config.SERPSTACK_API_KEY,
                    "query": keyword,
                    "gl": location,
                    "hl": language,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error"):
                raise SerpAPIError(f"Serpstack error: {data['error']}")
            return data

    def _mock_response(self, keyword: str) -> dict:
        """Reponse simulee pour le mode dry-run."""
        return {
            "keyword": keyword,
            "organic_results": [
                {
                    "position": i,
                    "title": f"Resultat simule #{i} pour {keyword}",
                    "url": f"https://exemple{i}.fr/article-{keyword.replace(' ', '-')}",
                    "snippet": f"Extrait de contenu simule pour '{keyword}' en position {i}.",
                }
                for i in range(1, 10)
            ],
            "related_questions": [
                f"Qu'est-ce que {keyword} ?",
                f"Comment fonctionne {keyword} ?",
                f"Pourquoi {keyword} est important ?",
                f"Quels sont les avantages de {keyword} ?",
            ],
            "featured_snippet": {
                "title": f"Definition de {keyword}",
                "content": f"Contenu simule du featured snippet pour {keyword}.",
            },
            "ai_overview": {
                "content": f"Resume IA simule pour {keyword}.",
            },
        }
