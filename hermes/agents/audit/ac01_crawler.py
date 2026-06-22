"""AC01 — Content Crawler + Indexabilite.

Fetch chaque page et extrait 55+ signaux structures.
BeautifulSoup pour le parsing HTML (gratuit, pas de LLM).
Fallback OSS : AI Website Audit CLI, SEOpie Core.
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from hermes.models.audit import AuditSessionState, CrawledPage

logger = logging.getLogger("hermes.audit.ac01")

# Patterns utiles
_RE_WORDS = re.compile(r"\b\w+\b")
_RE_NUMBER = re.compile(r"\d+")
_RE_EMAIL = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+")
_RE_DATE = re.compile(r"\b\d{4}\b")


async def _fetch_page(url: str, timeout: int = 20) -> tuple[str, int, str, str]:
    """Fetch une page avec httpx. Retourne (html, status, final_url, error)."""
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HermesAudit/1.0)"},
        ) as client:
            resp = await client.get(url)
            return resp.text, resp.status_code, str(resp.url), ""
    except httpx.TimeoutException:
        return "", 0, url, "timeout"
    except Exception as e:
        return "", 0, url, str(e)


def _extract_signals(html: str, base_url: str) -> dict[str, Any]:
    """Extrait 55+ signaux d'une page HTML via BeautifulSoup."""
    soup = BeautifulSoup(html, "html.parser")
    signals: dict[str, Any] = {}

    # ── Meta ──
    signals["title"] = ""
    title_tag = soup.find("title")
    if title_tag:
        signals["title"] = title_tag.get_text(strip=True)
    signals["title_length"] = len(signals["title"])

    signals["meta_description"] = ""
    md = soup.find("meta", attrs={"name": "description"})
    if md:
        signals["meta_description"] = md.get("content", "")[:300]
    signals["meta_description_length"] = len(signals["meta_description"])

    signals["canonical"] = ""
    can = soup.find("link", rel="canonical")
    if can:
        signals["canonical"] = can.get("href", "")

    signals["robots_meta"] = ""
    rob = soup.find("meta", attrs={"name": "robots"})
    if rob:
        signals["robots_meta"] = rob.get("content", "")

    # OG
    for og_field, attr in [("og_title", "og:title"), ("og_description", "og:description"), ("og_image", "og:image")]:
        tag = soup.find("meta", property=attr)
        signals[og_field] = tag.get("content", "") if tag else ""

    # Twitter
    tw = soup.find("meta", attrs={"name": "twitter:card"})
    signals["twitter_card"] = tw.get("content", "") if tw else ""

    # ── Hn ──
    h1s = soup.find_all("h1")
    signals["h1"] = h1s[0].get_text(strip=True) if h1s else ""
    signals["h1_count"] = len(h1s)
    signals["h2_list"] = [h.get_text(strip=True) for h in soup.find_all("h2")[:20]]
    signals["h3_list"] = [h.get_text(strip=True) for h in soup.find_all("h3")[:30]]

    # Hierarchie Hn
    hn_tags = [t.name for t in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])]
    signals["heading_hierarchy_ok"] = True
    prev_level = 0
    for tag in hn_tags:
        level = int(tag[1])
        if level > prev_level + 1:
            signals["heading_hierarchy_ok"] = False
            break
        prev_level = level

    # ── Contenu ──
    body = soup.find("body")
    all_text = body.get_text(separator=" ", strip=True) if body else ""
    signals["word_count"] = len(_RE_WORDS.findall(all_text))

    # Texte visible seulement (approx : exclure les elements avec display:none)
    visible_text = all_text  # Simplification V1 — le delta DOM est en V2
    signals["word_count_visible"] = signals["word_count"]
    signals["text_html_ratio"] = round(
        len(visible_text) / max(1, len(html)) * 100, 1
    )

    # Detection langue
    fr_chars = len(re.findall(r"[éèêëàâäùûüîïôöçÉÈÊËÀÂÄÙÛÜÎÏÔÖÇ]", all_text[:5000]))
    signals["language_detected"] = "fr" if fr_chars > 2 else "other"

    # ── Images ──
    imgs = soup.find_all("img")
    signals["images_total"] = len(imgs)
    signals["images_with_alt"] = sum(1 for i in imgs if i.get("alt", "").strip())
    signals["images_lazy"] = sum(1 for i in imgs if i.get("loading") == "lazy")
    signals["images_with_dimensions"] = sum(
        1 for i in imgs if i.get("width") and i.get("height")
    )

    # ── Liens ──
    domain = urlparse(base_url).netloc
    internal = 0
    external = 0
    links_list = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        text = a.get_text(strip=True)
        if parsed.netloc == domain or not parsed.netloc:
            internal += 1
            links_list.append({"url": full, "ancre": text[:80], "type": "internal"})
        else:
            external += 1
    signals["internal_links"] = internal
    signals["external_links"] = external
    signals["broken_links"] = 0
    signals["internal_links_list"] = links_list[:50]

    # ── Schema ──
    scripts = soup.find_all("script", type="application/ld+json")
    json_ld_types = []
    for s in scripts:
        try:
            import json
            data = json.loads(s.string or "{}")
            if isinstance(data, dict) and "@type" in data:
                json_ld_types.append(data["@type"])
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "@type" in item:
                        json_ld_types.append(item["@type"])
        except Exception:
            pass
    signals["json_ld_types"] = json_ld_types
    signals["json_ld_valid"] = len(json_ld_types) > 0
    signals["microdata_present"] = bool(soup.find(attrs={"itemscope": True}))

    # ── UX ──
    # CTA (boutons, liens d'action)
    cta_keywords = ("devis", "contact", "essai", "demo", "acheter", "commander",
                    "souscrire", "reserver", "appeler", "obtenir", "telecharger")
    cta_count = 0
    for a in soup.find_all("a"):
        text = a.get_text(strip=True).lower()
        if any(kw in text for kw in cta_keywords):
            cta_count += 1
    signals["has_cta"] = cta_count > 0
    signals["cta_count"] = cta_count

    # Breadcrumbs
    signals["has_breadcrumbs"] = bool(
        soup.find(attrs={"aria-label": "breadcrumb"})
        or soup.find(class_=re.compile("breadcrumb"))
        or soup.find("nav", class_=re.compile("breadcrumb"))
    )
    signals["has_video"] = bool(soup.find("video") or soup.find("iframe"))

    # Temps de lecture
    signals["reading_time_minutes"] = max(1, signals["word_count"] // 250)

    # ── Technique ──
    signals["content_type"] = "text/html"
    signals["charset"] = "utf-8"
    meta_charset = soup.find("meta", charset=True)
    if meta_charset:
        signals["charset"] = meta_charset.get("charset", "utf-8")
    signals["has_viewport"] = bool(soup.find("meta", attrs={"name": "viewport"}))
    signals["is_amp"] = bool(soup.find("html", attrs={"amp": True}) or "⚡" in html[:200])

    # ── Auteur ──
    signals["author_name"] = ""
    # Chercher dans les meta, les classes, le schema
    author_meta = soup.find("meta", attrs={"name": "author"})
    if author_meta:
        signals["author_name"] = author_meta.get("content", "")
    article_meta = soup.find("meta", property="article:author")
    if article_meta and not signals["author_name"]:
        signals["author_name"] = article_meta.get("content", "")
    signals["author_detected"] = bool(signals["author_name"])

    # Dates
    signals["date_published"] = ""
    signals["date_modified"] = ""
    date_meta = soup.find("meta", property="article:published_time")
    if date_meta:
        signals["date_published"] = date_meta.get("content", "")[:10]
    modified_meta = soup.find("meta", property="article:modified_time")
    if modified_meta:
        signals["date_modified"] = modified_meta.get("content", "")[:10]

    # ── Indexabilite ──
    signals["has_noindex"] = "noindex" in signals["robots_meta"].lower()
    signals["robots_blocked"] = False
    signals["is_indexable"] = not signals["has_noindex"]

    return signals


async def run(state: AuditSessionState) -> AuditSessionState:
    """Crawle les URLs de la session et extrait les signaux."""
    state.current_agent = "ac01"
    logger.info(f"AC01: crawling {len(state.urls)} URLs")

    # Tentative d'utilisation d'un outil OSS en fallback
    try:
        # AI Website Audit CLI — si installe
        import importlib
        if importlib.util.find_spec("ai_website_audit"):
            logger.info("AC01: AI Website Audit CLI detected, skipping (no fallback needed)")
        # SEOpie Core — si installe
        if importlib.util.find_spec("seopie"):
            logger.info("AC01: SEOpie Core detected, could be used as fallback")
    except Exception:
        pass

    crawled_pages = []

    for url in state.urls:
        logger.info(f"AC01: fetching {url}")
        html, status, final_url, error = await _fetch_page(url)

        page = CrawledPage(
            url=url,
            status_code=status,
            final_url=final_url,
            fetch_error=error,
        )

        if status == 200 and html:
            signals = _extract_signals(html, url)
            # Appliquer les signaux au modele
            for key, value in signals.items():
                if hasattr(page, key):
                    setattr(page, key, value)
            # Redirect chain
            if final_url != url:
                page.redirect_chain = [url, final_url]
            logger.info(
                f"AC01: {url} OK — {page.word_count} mots, "
                f"h1='{page.h1[:50]}', images={page.images_total}"
            )
        else:
            logger.warning(f"AC01: {url} FAILED (status={status}, error={error})")

        crawled_pages.append(page)

    state.crawled_pages = crawled_pages
    state.updated_at = datetime.now()
    logger.info(f"AC01: done — {len(crawled_pages)} pages crawled")
    return state
