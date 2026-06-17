"""Connecteur SERP API — TalorData, Scrape.do et Serpstack.

Trois fournisseurs supportes avec fallback automatique.
Priorite (juin 2026) : TalorData > Scrape.do > Serpstack.

Sources :
- https://dev.to/talordata_elowen/2026-serp-api-comparison
- https://scrape.do/blog/google-serp-api/
"""

import json
from typing import Optional
from urllib.parse import urlparse

import httpx

from hermes import config
from hermes.core.exceptions import SerpAPIError


def _extract_domain_static(url: str) -> str:
    """Extrait le domaine net d'une URL."""
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return url.lower()


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
        """Appelle l'API TalorData et normalise la reponse en format Hermes.

        L'API retourne du JSON structure (json=2) avec:
        - organic: resultats organiques (title, link, description)
        - related: questions "People Also Ask" (text, link)
        - snack_pack: entreprises locales (Google Maps)
        - search_information: infos de recherche
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://serpapi.talordata.net/serp/v1/request",
                headers={
                    "Authorization": f"Bearer {config.TALORDATA_API_KEY}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "q": keyword,
                    "engine": "google",
                    "hl": language,
                    "gl": location,
                    "num": "10",
                    "json": "2",
                },
            )
            resp.raise_for_status()
            wrapper = resp.json()

        if wrapper.get("code") != 0:
            raise SerpAPIError(
                f"TalorData error {wrapper.get('code')}: {wrapper.get('data', '')}"
            )

        raw = json.loads(wrapper["data"]["json"])
        return self._normalize_talordata(raw, keyword)

    def _normalize_talordata(self, raw: dict, keyword: str) -> dict:
        """Convertit le format TalorData vers le format Hermes standard.

        TalorData: {organic: [{title, link, description, display_link}],
                     related: [{text, link}],
                     snack_pack: [{name, address, reviews, ...}]}
        Hermes:    {organic_results: [{position, title, url, snippet}],
                     related_questions: [str],
                     featured_snippet: dict,
                     ai_overview: dict}
        """
        # Resultats organiques
        organic_results = []
        for i, item in enumerate(raw.get("organic", [])[:10]):
            url = item.get("link", "")
            organic_results.append({
                "position": i + 1,
                "title": item.get("title", ""),
                "url": url,
                "snippet": item.get("description", item.get("snippet", "")),
                "domain": _extract_domain_static(url),
                "display_link": item.get("display_link", ""),
            })

        # People Also Ask
        related = [
            q.get("text", q.get("question", ""))
            for q in raw.get("related", [])[:10]
            if q.get("text") or q.get("question")
        ]

        # Featured snippet (via answer_box TalorData)
        fs = raw.get("answer_box") or {}
        featured_snippet = {}
        if fs.get("title") or fs.get("snippet"):
            featured_snippet = {
                "title": fs.get("title", ""),
                "content": fs.get("snippet", fs.get("answer", "")),
            }

        # AI Overview
        ai = raw.get("ai_overview") or {}
        ai_overview = {}
        if ai.get("text") or ai.get("snippet"):
            ai_overview = {
                "content": ai.get("text", ai.get("snippet", "")),
            }

        # Search info
        search_info = raw.get("search_information") or {}
        total = search_info.get("total_results")
        total_results = None
        if isinstance(total, int):
            total_results = total
        elif isinstance(total, str) and total.isdigit():
            total_results = int(total)

        # Snack pack (local)
        snack_pack = raw.get("snack_pack") or []

        return {
            "keyword": keyword,
            "organic_results": organic_results,
            "related_questions": related,
            "featured_snippet": featured_snippet,
            "ai_overview": ai_overview,
            "total_results": total_results,
            "snack_pack": snack_pack,
        }

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
