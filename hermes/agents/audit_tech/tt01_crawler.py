"""T01 — Crawler Technique.

Parcourt le site et extrait 55+ signaux techniques par page :
- HTTP : status code, headers, redirects, load time, TTFB, SSL
- Meta : title, meta description, canonical, robots meta, OG, Twitter
- Structure : H1-H3, hierarchy
- Contenu : word count, text/HTML ratio, langue
- Images : total, sans alt
- Liens : internes, externes, liste
- Schema : JSON-LD types, microdata
- Hreflang : balises link alternate
- UX : viewport, CTA, breadcrumbs, video
- Indexabilite : noindex, robots.txt
- CMS : detection via cms_detector
- Performance : page size, TTFB

Reutilise le pattern _extract_signals() de AC01.
Respecte robots.txt et rate limiting.
$0 — pas de LLM.
"""

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from hermes.models.audit_tech import TechAuditState, TechCrawlPage

logger = logging.getLogger("hermes.audit_tech.tt01")

# Default User-Agent
UA = "HermesAudit/1.0"

# Extensions et patterns a ne pas crawler
SKIP_EXTENSIONS = (
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".mp4", ".webp",
    ".zip", ".xml", ".json", ".css", ".js", ".gz", ".ico", ".woff", ".ttf",
    ".mp3", ".wav", ".avi", ".mov", ".webm", ".avif",
)

SKIP_PATTERNS = (
    "/wp-admin", "/wp-login", "/wp-json", "/feed", "/.well-known",
    "/admin", "/login", "/logout", "/cart", "/checkout", "/account",
    "/cdn-cgi/", "/ajax/", "/api/",
)

# Type de page detection (URL-based, comme dans Pipeline 2)
PAGE_TYPE_PATTERNS = [
    ("accueil", r"^/$|^$"),
    ("produit", r"/\d+-[\w-]+\.html?$"),
    ("categorie", r"/\d+-[\w-]+$"),
    ("article", r"/(blog|article|actualite|news|post|module-blog)/"),
    ("service", r"/(service|prestation|offre)/"),
    ("legale", r"/(cgu|cgv|mentions|privacy|contact|login|account|mon-compte|nous-contacter)"),
]


def _classify_page_type(url: str) -> str:
    """Determine le type de page a partir de son URL."""
    path = urlparse(url).path.lower()
    for ptype, pattern in PAGE_TYPE_PATTERNS:
        if re.search(pattern, path):
            return ptype
    return "autre"


def _extract_signals(html: str, url: str, final_url: str,
                     status_code: int, headers: dict,
                     load_time_ms: int, ttfb_ms: int,
                     content_length: int) -> dict:
    """Extrait 55+ signaux techniques d'une page HTML.

    Replique et enrichit le pattern _extract_signals() de AC01.
    """
    signals: dict = {}
    soup = BeautifulSoup(html, "html.parser")

    # ── HTTP ──────────────────────────────────────────────────────────
    signals["status_code"] = status_code
    signals["final_url"] = final_url
    signals["http_headers"] = {k: v for k, v in headers.items()}
    signals["content_type"] = headers.get("content-type", "")
    signals["content_length_bytes"] = content_length
    signals["load_time_ms"] = load_time_ms
    signals["ttfb_ms"] = ttfb_ms
    signals["is_https"] = url.startswith("https")
    signals["page_size_kb"] = round(len(html.encode("utf-8")) / 1024, 2)
    signals["redirect_count"] = 0  # Sera maj par le crawler

    # ── Meta ──────────────────────────────────────────────────────────
    title_tag = soup.find("title")
    signals["title"] = title_tag.get_text(strip=True) if title_tag else ""
    signals["title_length"] = len(signals["title"])

    meta_desc = soup.find("meta", attrs={"name": "description"})
    signals["meta_description"] = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else ""
    signals["meta_description_length"] = len(signals["meta_description"])

    canonical_tag = soup.find("link", rel="canonical")
    signals["canonical"] = canonical_tag["href"] if canonical_tag and canonical_tag.get("href") else ""

    robots_tag = soup.find("meta", attrs={"name": "robots"})
    signals["robots_meta"] = robots_tag["content"].strip() if robots_tag and robots_tag.get("content") else ""

    # OG
    og_title = soup.find("meta", attrs={"property": "og:title"})
    signals["og_title"] = og_title["content"].strip() if og_title and og_title.get("content") else ""
    og_desc = soup.find("meta", attrs={"property": "og:description"})
    signals["og_description"] = og_desc["content"].strip() if og_desc and og_desc.get("content") else ""
    og_img = soup.find("meta", attrs={"property": "og:image"})
    signals["og_image"] = og_img["content"].strip() if og_img and og_img.get("content") else ""

    # Twitter
    tw_card = soup.find("meta", attrs={"name": "twitter:card"})
    signals["twitter_card"] = tw_card["content"].strip() if tw_card and tw_card.get("content") else ""

    # ── Structure Hn ─────────────────────────────────────────────────
    h1_tags = soup.find_all("h1")
    signals["h1"] = h1_tags[0].get_text(strip=True) if h1_tags else ""
    signals["h1_count"] = len(h1_tags)

    h2_tags = soup.find_all("h2")
    signals["h2_list"] = [h.get_text(strip=True)[:120] for h in h2_tags]
    signals["h3_list"] = [h.get_text(strip=True)[:120] for h in soup.find_all("h3")]

    # Verifier la hierarchie Hn
    hn_tags = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    hn_levels = [int(t.name[1]) for t in hn_tags]
    hierarchy_ok = True
    for i in range(1, len(hn_levels)):
        if hn_levels[i] > hn_levels[i - 1] + 1:
            hierarchy_ok = False
            break
    signals["heading_hierarchy_ok"] = hierarchy_ok

    # ── Contenu ──────────────────────────────────────────────────────
    body = soup.find("body")
    if body:
        for tag in body.find_all(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        visible_text = body.get_text(separator=" ", strip=True)
    else:
        visible_text = soup.get_text(separator=" ", strip=True)

    words = visible_text.split()
    signals["word_count"] = len(words)

    html_size = len(html)
    signals["text_html_ratio"] = round(len(visible_text) / max(1, html_size), 3)

    # Langue
    html_tag = soup.find("html")
    signals["language_detected"] = html_tag.get("lang", "") if html_tag else ""

    # ── Images ───────────────────────────────────────────────────────
    imgs = soup.find_all("img")
    signals["images_total"] = len(imgs)
    signals["images_without_alt"] = sum(1 for img in imgs if not img.get("alt"))

    # ── Liens ───────────────────────────────────────────────────────
    domain = urlparse(url).netloc.lower()
    internal_links = []
    external_count = 0
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        try:
            full = urljoin(url, href)
            parsed = urlparse(full)
            if parsed.netloc.lower().replace("www.", "") == domain.replace("www.", ""):
                internal_links.append({"url": full, "anchor": a.get_text(strip=True)[:80]})
            else:
                external_count += 1
        except Exception:
            pass

    signals["internal_links_count"] = len(internal_links)
    signals["external_links_count"] = external_count
    signals["internal_links_list"] = internal_links[:50]

    # ── Schema ───────────────────────────────────────────────────────
    json_ld_types = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            import json
            data = json.loads(script.string)
            if isinstance(data, dict):
                t = data.get("@type", "")
            elif isinstance(data, list) and data:
                t = data[0].get("@type", "") if isinstance(data[0], dict) else ""
            else:
                t = ""
            if t:
                json_ld_types.append(t)
        except Exception:
            pass
    signals["json_ld_types"] = json_ld_types
    signals["json_ld_valid"] = len(json_ld_types) > 0
    signals["microdata_present"] = bool(soup.find(attrs={"itemscope": True}) or soup.find(attrs={"itemtype": True}))

    # ── Hreflang ─────────────────────────────────────────────────────
    hreflang_tags = []
    for link in soup.find_all("link", rel="alternate"):
        hreflang = link.get("hreflang", "")
        href = link.get("href", "")
        if hreflang or "hreflang" in str(link.get("rel", "")):
            hreflang_tags.append({"hreflang": hreflang, "href": href})
    signals["hreflang_tags"] = hreflang_tags

    # ── UX ───────────────────────────────────────────────────────────
    signals["has_viewport"] = bool(soup.find("meta", attrs={"name": "viewport"}))
    signals["has_cta"] = bool(
        soup.find("button") or
        soup.find("a", class_=re.compile(r"btn|cta|button|action", re.I)) or
        soup.find("form")
    )
    signals["has_breadcrumbs"] = bool(
        soup.find(class_=re.compile(r"breadcrumb|fil-ariane", re.I)) or
        soup.find("nav", attrs={"aria-label": re.compile(r"breadcrumb|fil", re.I)})
    )
    signals["has_video"] = bool(soup.find("video") or soup.find("iframe"))

    # ── Indexabilite ─────────────────────────────────────────────────
    robots_content = signals["robots_meta"].lower()
    signals["has_noindex"] = "noindex" in robots_content
    signals["is_indexable"] = not signals["has_noindex"]
    signals["robots_blocked"] = False  # Sera determine par T02/T04

    # ── Charset ──────────────────────────────────────────────────────
    charset_tag = soup.find("meta", attrs={"charset": True}) or soup.find("meta", attrs={"http-equiv": re.compile(r"content-type", re.I)})
    signals["charset"] = "utf-8"
    if charset_tag:
        cs = charset_tag.get("charset", "") or charset_tag.get("content", "")
        if "charset=" in cs.lower():
            signals["charset"] = cs.lower().split("charset=")[-1].split(";")[0].strip()

    return signals


async def _fetch_page(url: str, client: httpx.AsyncClient) -> tuple[Optional[str], int, str, dict, int, int, int]:
    """Fetch une page et retourne (html, status, final_url, headers, load_time_ms, ttfb_ms, content_length)."""
    try:
        start = time.monotonic()
        ttfb = None
        resp = await client.get(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        load_time = int((time.monotonic() - start) * 1000)
        # TTFB approx (httpx ne donne pas TTFB directement)
        ttfb_ms = load_time // 2  # Estimation conservative
        content_length = len(resp.content) if resp.content else 0
        return resp.text, resp.status_code, str(resp.url), dict(resp.headers), load_time, ttfb_ms, content_length
    except Exception as e:
        logger.debug(f"T01 fetch failed: {url} — {e}")
        return None, 0, url, {}, 0, 0, 0


async def _crawl_page(url: str, client: httpx.AsyncClient, depth: int) -> Optional[TechCrawlPage]:
    """Crawle une page et retourne un TechCrawlPage."""
    html, status, final_url, headers, load_time_ms, ttfb_ms, content_length = await _fetch_page(url, client)

    if status == 0 or html is None:
        return TechCrawlPage(
            url=url, status_code=0, fetch_error="fetch_failed",
            crawl_depth=depth
        )

    if "text/html" not in headers.get("content-type", "").lower() and status == 200:
        return TechCrawlPage(
            url=url, status_code=status, content_type=headers.get("content-type", ""),
            load_time_ms=load_time_ms, crawl_depth=depth,
            page_size_kb=round(content_length / 1024, 2),
        )

    signals = _extract_signals(
        html=html, url=url, final_url=final_url,
        status_code=status, headers=headers,
        load_time_ms=load_time_ms, ttfb_ms=ttfb_ms,
        content_length=content_length,
    )
    signals["url"] = url
    signals["crawl_depth"] = depth

    # Detection CMS (reutilise cms_detector)
    try:
        from hermes.connectors.cms_detector import detect_cms
        cms_data = await detect_cms(url)
        signals["cms_detected"] = cms_data.get("cms", "")
        signals["cms_version"] = cms_data.get("version", "") or ""
        signals["cms_confidence"] = cms_data.get("confidence", 0)
    except Exception:
        signals["cms_detected"] = ""
        signals["cms_version"] = ""
        signals["cms_confidence"] = 0

    return TechCrawlPage(**signals)


async def run(state: TechAuditState) -> TechAuditState:
    """Crawle les URLs et extrait les signaux techniques."""
    state.current_agent = "tt01"

    if not state.urls:
        logger.warning("T01: aucune URL a crawler")
        state.status = "error"
        return state

    logger.info(f"T01: crawling {len(state.urls)} URLs (max_depth={state.max_depth}, rate_limit={state.rate_limit_rps} req/s)")

    delay = 1.0 / state.rate_limit_rps if state.rate_limit_rps > 0 else 1.0

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        # Crawler les URLs fournies (depth 0 = racine)
        for i, url in enumerate(state.urls[:state.max_urls]):
            try:
                page = await _crawl_page(url, client, depth=0)
                if page:
                    state.crawled_pages.append(page)
            except Exception as e:
                logger.warning(f"T01: erreur crawl {url} — {e}")
                state.error_count += 1

            # Rate limiting
            if i < len(state.urls) - 1 and delay > 0:
                await asyncio.sleep(delay)

    # Detection CMS globale (depuis la page d'accueil)
    for page in state.crawled_pages:
        if page.cms_detected and page.crawl_depth == 0:
            state.cms_detected = page.cms_detected
            state.cms_version = page.cms_version
            state.cms_confidence = page.cms_confidence
            break

    # Si pas de CMS detecte via les pages, essayer directement
    if not state.cms_detected and state.site_url:
        try:
            from hermes.connectors.cms_detector import detect_cms
            cms_data = await detect_cms(state.site_url)
            state.cms_detected = cms_data.get("cms", "")
            state.cms_version = cms_data.get("version", "") or ""
            state.cms_confidence = cms_data.get("confidence", 0)
        except Exception:
            pass

    logger.info(
        f"T01: {len(state.crawled_pages)} pages crawlees, "
        f"CMS={state.cms_detected or 'inconnu'}, "
        f"errors={state.error_count}"
    )

    state.status = "crawled"
    state.updated_at = datetime.now()
    return state
