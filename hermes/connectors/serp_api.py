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
            try:
                return await self._search_serpstack(keyword, location, language)
            except SerpAPIError:
                pass

        # Filet de securite : recherche web gratuite (DuckDuckGo HTML)
        # Indispensable pour contextualiser un mot-cle avant la redaction
        try:
            return await self._search_duckduckgo(keyword, location, language)
        except Exception as e:
            raise SerpAPIError(
                f"Aucune API SERP disponible (TalorData/Scrape.do/Serpstack KO et "
                f"DuckDuckGo fallback echec: {e}). Le mot-cle ne pourra pas etre "
                f"contextualise. Refusez la generation sans recherche web."
            )

    async def _search_duckduckgo(
        self, keyword: str, location: str, language: str
    ) -> dict:
        """Fallback gratuit via DuckDuckGo HTML (pas de cle API requise).

        Cle pour Hermes : meme sans API SERP payante, on obtient un contexte
        semantique du mot-cle (top 10 titres + descriptions + domaines).
        C'est la difference entre "nano banana = fruit" et "nano banana = IA Google".

        Strategie: 2 endpoints + 3 user-agents pour resilience.
        """
        import re as _re
        import asyncio as _asyncio

        params = {
            "q": keyword,
            "kl": f"{location}-{language}" if location != language else f"{language}-{language}",
        }

        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        ]
        endpoints = [
            "https://html.duckduckgo.com/html/",
            "https://duckduckgo.com/html/",
            "https://duckduckgo.com/html",
        ]

        html = ""
        last_err = None
        for ua in user_agents:
            headers = {
                "User-Agent": ua,
                "Accept-Language": f"{language}-{language.upper()},{language};q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
            for url in endpoints:
                try:
                    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                        resp = await client.get(url, params=params, headers=headers)
                        if resp.status_code == 200 and len(resp.text) > 1000:
                            html = resp.text
                            break
                except Exception as e:
                    last_err = e
                    continue
            if html:
                break
            await _asyncio.sleep(0.5)

        if not html:
            raise SerpAPIError(f"DuckDuckGo HTML inaccessible: {last_err}")

        # Parser les resultats (DuckDuckGo HTML format)
        # Strategie: capturer les blocs <div class="result results_links_deep web-result">
        # qui contiennent title (a.result__a), url (a.result__url), snippet (a.result__snippet)
        from urllib.parse import unquote, parse_qs, urlparse
        from html import unescape

        results = []
        # Decouper en blocs de resultats
        blocks = _re.split(r'<div[^>]+class="[^"]*result[^"]*results_links_deep[^"]*"', html)
        for i, block in enumerate(blocks[1:25], 1):  # Skip first empty
            # Title + URL
            m_title = _re.search(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                block, _re.DOTALL,
            )
            if not m_title:
                continue
            raw_url = m_title.group(1)
            title_raw = m_title.group(2)
            # Snippet
            m_snippet = _re.search(
                r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>',
                block, _re.DOTALL,
            )
            snippet_raw = m_snippet.group(1) if m_snippet else ""

            # Decoder l'URL DuckDuckGo
            clean_url = raw_url
            if "uddg=" in raw_url or "duckduckgo.com/l/" in raw_url:
                try:
                    if raw_url.startswith("//"):
                        raw_url = "https:" + raw_url
                    parsed_url = urlparse(raw_url if raw_url.startswith("http") else "https://duckduckgo.com" + raw_url)
                    qs = parse_qs(parsed_url.query)
                    if "uddg" in qs:
                        clean_url = unquote(qs["uddg"][0])
                except Exception:
                    pass

            # Nettoyer title et snippet (decoder HTML entities + retirer balises)
            title_clean = unescape(_re.sub(r"<[^>]+>", "", title_raw)).strip()
            snippet_clean = unescape(_re.sub(r"<[^>]+>", "", snippet_raw)).strip()

            # Domaine reel
            domain = _extract_domain_static(clean_url)
            if domain == "duckduckgo.com" or not domain:
                continue  # Skip si URL non resolue

            if title_clean:
                results.append({
                    "position": i,
                    "title": title_clean,
                    "url": clean_url,
                    "snippet": snippet_clean,
                    "domain": domain,
                })

        if not results:
            raise SerpAPIError("DuckDuckGo fallback: aucun resultat parsable")

        # Format normalise Hermes
        return {
            "organic_results": results,
            "related_questions": [],
            "featured_snippet": None,
            "ai_overview": None,
            "source": "duckduckgo_html_fallback",
            "keyword": keyword,
        }

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
