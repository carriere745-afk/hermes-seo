"""Sitemap parser BFS — porte depuis saas-seo/app/api/audit/content/sitemap/route.js.

Auto-detection robots.txt + candidats + BFS depth 3.
$0 — pas de LLM, pas d'API payante.
"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger("hermes.sitemap")

# Candidats sitemap a tester dans l'ordre (standards + CMS specifiques)
SITEMAP_CANDIDATES = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemap/sitemap.xml",
    "/wp-sitemap.xml",           # WordPress 5.5+
    "/news-sitemap.xml",
    "/page-sitemap.xml",
    "/post-sitemap.xml",
    "/sitemap.xml.gz",
    "/1_index_sitemap.xml",      # PrestaShop
    "/2_index_sitemap.xml",      # PrestaShop (categories)
    "/fr/sitemap.xml",           # Multilingue
    "/sitemap_index.xml",        # Variante
    "/sitemap.php",              # CMS custom
]

# Filtres d'exclusion (extensions non-HTML)
EXCLUDED_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".mp4",
    ".zip", ".xml", ".json", ".css", ".js", ".gz", ".ico",
    ".woff", ".ttf", ".webp", ".avif", ".mp3", ".wav",
)

# Patterns d'URLs techniques (admin, login, etc.)
EXCLUDED_PATTERNS = (
    "/wp-admin", "/wp-login", "/wp-json", "/feed", "/.well-known",
    "/admin", "/login", "/logout", "/cart", "/checkout",
)


async def detect_sitemaps(base_url: str) -> dict:
    """Auto-detecte les sitemaps d'un site.

    1. robots.txt (via protego si dispo)
    2. Candidats classiques (HEAD request)

    Returns: {"found": bool, "urls": list, "source": str}
    """
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    # 0. Detector le CMS pour prioriser les candidats
    cms_candidates = []
    try:
        from hermes.connectors.cms_detector import detect_cms, CMS_SITEMAP_PRIORITY
        cms_data = await detect_cms(base_url)
        if cms_data.get("sitemap_candidates"):
            cms_candidates = cms_data["sitemap_candidates"]
            logger.info(f"CMS detected: {cms_data['cms']} (confidence {cms_data.get('confidence', 0)}%). "
                       f"Sitemap candidates: {cms_candidates}")
    except ImportError:
        pass

    # 1. Essayer robots.txt
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            robots_url = urljoin(base_url, "/robots.txt")
            resp = await client.get(robots_url, headers={"User-Agent": "HermesAudit/1.0"})
            if resp.status_code == 200:
                text = resp.text
                # Extraire les Sitemap: lignes
                sitemaps = re.findall(r"(?i)sitemap:\s*(.+)", text)
                if sitemaps:
                    logger.info(f"Sitemaps trouves via robots.txt: {len(sitemaps)}")
                    return {
                        "found": True,
                        "urls": [s.strip() for s in sitemaps],
                        "source": "robots.txt",
                    }
    except Exception:
        pass

    # 2. Tester les candidats (CMS d'abord, puis generiques)
    candidates_to_test = cms_candidates + [c for c in SITEMAP_CANDIDATES if c not in cms_candidates]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for path in candidates_to_test:
            try:
                url = urljoin(base_url, path)
                # Essayer GET avant HEAD (certains serveurs refusent HEAD)
                resp = await client.get(url, headers={"User-Agent": "HermesAudit/1.0", "Accept": "application/xml,text/xml,*/*"})
                if resp.status_code == 200:
                    return {
                        "found": True,
                        "urls": [url],
                        "source": "scan",
                    }
            except Exception:
                continue

    return {"found": False, "urls": [], "source": None}


async def parse_sitemap_recursive(
    sitemap_urls: list[str],
    base_url: str,
    max_urls: int = 2000,
    max_depth: int = 3,
    max_sitemaps: int = 30,
) -> tuple[list[str], dict[str, int], dict]:
    """Parse les sitemaps recursivement (BFS depth 3).

    Suit les sitemap index (<sitemapindex>) vers leurs enfants.

    Args:
        sitemap_urls: URLs des sitemaps a parser
        base_url: URL racine du site (pour filtrage domaine)
        max_urls: nombre max d'URLs a retourner
        max_depth: profondeur max de recursion (sitemap index)
        max_sitemaps: nombre max de sitemaps a traiter

    Returns: (urls, typeDistribution, meta)
    """
    domain = urlparse(base_url).netloc.lower()

    async def _fetch_sitemap(url: str) -> dict:
        """Fetch un sitemap et extrait les URLs + detection index.

        Gere les formats : standard, Google, PrestaShop (CDATA), Yoast, RankMath.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    url,
                    headers={"User-Agent": "HermesAudit/1.0", "Accept": "application/xml,text/xml,*/*"},
                    follow_redirects=True,
                )
                if resp.status_code != 200:
                    logger.warning(f"Sitemap {url} → HTTP {resp.status_code}")
                    return {"urls": [], "is_index": False}
                xml = resp.text

                # Detection sitemap index
                is_index = bool(re.search(r"<sitemapindex", xml, re.IGNORECASE))

                # Extraction URLs — approche robuste multi-etapes
                clean_urls = []

                # 1. Extraction directe : <loc>URL</loc>
                for m in re.finditer(r"<loc>(.*?)</loc>", xml, re.IGNORECASE | re.DOTALL):
                    content = m.group(1).strip()
                    # Retirer wrapper CDATA
                    for pattern in (r"<!\[CDATA\[(.*?)\]\]>", r"<!\[CDATA\[(.*?)\]\]", r"\[CDATA\[(.*?)\]\]>"):
                        cm = re.search(pattern, content, re.DOTALL)
                        if cm:
                            content = cm.group(1).strip()
                            break
                    if content.startswith("http"):
                        clean_urls.append(content)

                # 2. Fallback : extraire les URLs depuis les blocs CDATA
                if not clean_urls:
                    for m in re.finditer(r"<!\[CDATA\[(https?://[^\]]*?)\]\]>", xml):
                        clean_urls.append(m.group(1).strip())

                # 3. Fallback ultime : toute URL du domaine
                if not clean_urls:
                    all_urls = re.findall(r"https?://[^\s><\"'&]+", xml)
                    clean_urls = [u for u in all_urls if not u.endswith(('.jpg', '.png', '.gif', '.svg', '.css', '.js'))]

                # Deduplicate
                clean_urls = list(dict.fromkeys(clean_urls))

                logger.info(f"Sitemap {url}: {'index' if is_index else 'urlset'} → {len(clean_urls)} URLs")
                return {"urls": clean_urls, "is_index": is_index}
        except Exception as e:
            logger.warning(f"Sitemap fetch failed: {url} — {e}")
            return {"urls": [], "is_index": False}

    # BFS
    queue = [{"url": u, "depth": 0} for u in sitemap_urls[:3]]
    seen = set()
    all_urls = []

    processed = 0
    while queue and processed < max_sitemaps:
        item = queue.pop(0)
        url, depth = item["url"], item["depth"]

        if url in seen:
            continue
        seen.add(url)
        processed += 1

        result = await _fetch_sitemap(url)

        if result["is_index"] and depth < max_depth:
            for child_url in result["urls"]:
                if child_url not in seen:
                    queue.append({"url": child_url, "depth": depth + 1})
        else:
            all_urls.extend(result["urls"])

    # Filtrer
    filtered = _filter_urls(all_urls, domain, max_urls)
    type_distribution = _classify_urls(filtered)
    meta = {
        "total_found": len(all_urls),
        "total_filtered": len(filtered),
        "sitemaps_processed": processed,
        "estimated_cost": round(len(filtered) * 0.003, 2),
        "estimated_minutes": max(1, len(filtered) // 30),
    }

    return filtered, type_distribution, meta


def _filter_urls(urls: list[str], domain: str, max_urls: int) -> list[str]:
    """Filtre les URLs : meme domaine, pas de fichiers, pas de pages techniques."""
    seen = set()
    filtered = []

    for url in urls:
        if len(filtered) >= max_urls:
            break
        try:
            u = urlparse(url)
            if u.netloc.lower() != domain:
                continue
            if any(u.path.lower().endswith(ext) for ext in EXCLUDED_EXTENSIONS):
                continue
            if any(p in u.path.lower() for p in EXCLUDED_PATTERNS):
                continue
            if "sitemap" in u.path.lower():
                continue
            if url in seen:
                continue
            seen.add(url)
            filtered.append(url)
        except Exception:
            continue

    return filtered


def _classify_urls(urls: list[str]) -> dict[str, int]:
    """Detecte les types de pages pour preview."""
    distribution = {}
    for url in urls:
        path = urlparse(url).path.lower()
        if path == "/" or path == "":
            page_type = "accueil"
        elif any(w in path for w in ("/blog/", "/article/", "/actualite/", "/news/", "/post/")):
            page_type = "articles"
        elif any(w in path for w in ("/service/", "/prestation/", "/offre/")):
            page_type = "services"
        elif any(w in path for w in ("/produit/", "/product/", "/shop/")):
            page_type = "produits"
        elif any(w in path for w in ("/categorie/", "/category/")):
            page_type = "categories"
        elif any(w in path for w in ("/faq/", "/questions/", "/glossaire/")):
            page_type = "FAQ"
        elif any(w in path for w in ("/cgu/", "/cgv/", "/mentions/", "/privacy/", "/contact/")):
            page_type = "legales"
        else:
            page_type = "autres"
        distribution[page_type] = distribution.get(page_type, 0) + 1

    return distribution


def crawl_from_homepage(base_url: str, max_pages: int = 50, max_depth: int = 3) -> list[str]:
    """Crawl BFS depuis la homepage.

    Parcourt les liens internes et retourne les URLs decouvertes,
    priorisant les pages proches de la racine (parentes → filles).

    Args:
        base_url: URL de depart
        max_pages: nombre max de pages a crawler
        max_depth: profondeur max de liens

    Returns: liste d'URLs decouvertes
    """
    import asyncio
    from urllib.parse import urljoin, urlparse
    import httpx
    from bs4 import BeautifulSoup

    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    domain = urlparse(base_url).netloc.lower()
    discovered = set()
    visited = set()
    queue = [(base_url, 0)]  # (url, depth)
    pages = []

    async def _crawl_one():
        """Version synchrone simplifiee pour V1."""
        import httpx as _httpx
        while queue and len(pages) < max_pages:
            url, depth = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            try:
                with _httpx.Client(timeout=10, follow_redirects=True) as client:
                    resp = client.get(url, headers={"User-Agent": "HermesAudit/1.0"})
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                pages.append(url)

                if depth < max_depth:
                    # Extraire les liens internes
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        full = urljoin(base_url, href)
                        parsed = urlparse(full)
                        # Meme domaine, pas de fragment, pas de fichier
                        if (parsed.netloc.lower() == domain
                                and full not in visited
                                and full not in discovered
                                and not parsed.path.endswith(('.pdf', '.jpg', '.png', '.gif', '.svg', '.mp4', '.zip'))
                                and '/wp-admin/' not in parsed.path
                                and '/wp-login' not in parsed.path
                                and '/cart' not in parsed.path
                                and '/checkout' not in parsed.path):
                            discovered.add(full)
                            queue.append((full, depth + 1))
            except Exception:
                continue

    _crawl_one()
    logger.info(f"BFS crawl: {len(pages)} pages discovered from {base_url}")
    return pages
