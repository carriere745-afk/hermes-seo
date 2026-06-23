"""Detecteur de CMS — fingerprinting rapide (headers, meta, patterns).

Avant de chercher le sitemap, on detecte le CMS pour :
1. Savoir exactement ou chercher le sitemap (PrestaShop ≠ WordPress ≠ Shopify)
2. Adapter les recommandations d'audit
3. Enrichir le rapport avec le contexte technique

$0 — pas de LLM, pas d'API. Headers HTTP + balises meta + patterns HTML.
"""

import logging
import re
from typing import Optional
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger("hermes.cms_detector")

# Signatures CMS : (nom, [(type, pattern, poids)])
CMS_SIGNATURES = {
    "PrestaShop": [
        ("header", r"PrestaShop", 50),
        ("meta", r'name="generator"[^>]*content="PrestaShop', 40),
        ("meta", r'name="generator"[^>]*content="prestashop', 40),
        ("cookie", r"PrestaShop-[a-f0-9]{10,64}", 50),
        ("html", r"/modules/|/themes/|prestashop", 30),
        ("html", r'id="prestashop"|class="prestashop"|class="ps_"', 20),
        ("html", r"prestashop\.com|addons\.prestashop", 15),
        ("sitemap", r"/\d+/_index_sitemap\.xml", 30),
    ],
    "WordPress": [
        ("header", r"WordPress", 40),
        ("html", r"/wp-content/|/wp-includes/|/wp-json/|wordpress", 40),
        ("file", r"/wp-login\.php", 20),
        ("sitemap", r"/wp-sitemap\.xml|/sitemap_index\.xml", 20),
    ],
    "Shopify": [
        ("meta", r"Shopify\.shop|shopify\.com", 40),
        ("html", r"myshopify\.com|cdn\.shopify\.com", 30),
        ("cookie", r"_shopify_", 20),
    ],
    "WooCommerce": [
        ("meta", r"WooCommerce", 30),
        ("html", r"/wp-content/plugins/woocommerce", 20),
        ("html", r"woocommerce", 15),
    ],
    "Magento": [
        ("meta", r"Magento", 40),
        ("html", r"/static/version\d+/|/pub/static/", 30),
        ("cookie", r"mage-", 20),
    ],
    "Drupal": [
        ("header", r"X-Drupal-", 40),
        ("meta", r"Drupal", 40),
        ("html", r"/sites/default/|/modules/contrib/", 20),
    ],
    "Joomla": [
        ("meta", r"Joomla!", 40),
        ("html", r"/components/com_|/modules/mod_", 20),
    ],
    "Wix": [
        ("meta", r"Wix\.com", 40),
        ("html", r"wix\.com|static\.wixstatic\.com", 30),
    ],
    "Squarespace": [
        ("meta", r"Squarespace", 40),
        ("html", r"squarespace\.com|static1\.squarespace\.com", 30),
    ],
    "Webflow": [
        ("meta", r"Webflow", 40),
        ("html", r"webflow\.com|assets\.website-files\.com", 30),
    ],
    "Ghost": [
        ("meta", r"Ghost", 40),
        ("html", r"/ghost/|/content/themes/", 20),
    ],
}

# Mapping CMS → candidats sitemap prioritaires
CMS_SITEMAP_PRIORITY = {
    "PrestaShop": ["/1_index_sitemap.xml", "/2_index_sitemap.xml", "/sitemap.xml"],
    "WordPress": ["/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml", "/sitemap-index.xml"],
    "Shopify": ["/sitemap.xml"],
    "Magento": ["/sitemap.xml", "/sitemap/sitemap.xml"],
    "Drupal": ["/sitemap.xml"],
    "Joomla": ["/sitemap.xml", "/sitemap.xml?format=xml"],
    "Wix": ["/sitemap.xml"],
    "Squarespace": ["/sitemap.xml"],
    "Webflow": ["/sitemap.xml"],
    "Ghost": ["/sitemap.xml"],
}


async def detect_cms(url: str) -> dict:
    """Detecte le CMS d'un site web.

    Args:
        url: URL du site (https://...)

    Returns: {
        "cms": "PrestaShop" | "WordPress" | "..." | "inconnu",
        "confidence": 0-100,
        "signals": [{"type": "header", "pattern": "PrestaShop", "weight": 50}, ...],
        "sitemap_candidates": ["/1_index_sitemap.xml", ...] | [],
        "version": "8.1" | null,
    }
    """
    result = {
        "cms": "inconnu",
        "confidence": 0,
        "signals": [],
        "sitemap_candidates": [],
        "version": None,
    }

    if not url.startswith("http"):
        url = f"https://{url}"

    UA = "HermesAudit/1.0"

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            # 1. HEAD pour les headers
            headers_data = {}
            try:
                head_resp = await client.head(url, headers={"User-Agent": UA})
                headers_data = dict(head_resp.headers)
            except Exception:
                pass

            # 2. GET pour le HTML (meta, patterns)
            html = ""
            all_headers = ""
            all_cookies = ""
            try:
                resp = await client.get(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
                if resp.status_code == 200:
                    html = resp.text
                    all_headers = str(resp.headers)
                    cookies_raw = resp.headers.get("set-cookie", "")
                    all_cookies = "; ".join(resp.headers.get_list("set-cookie")) if hasattr(resp.headers, "get_list") else cookies_raw
                else:
                    logger.debug(f"CMS detector: GET {url} → {resp.status_code}, falling back to robots.txt only")
            except Exception as e:
                logger.debug(f"CMS detector: GET failed ({e}), falling back to robots.txt")

            # 2.5 Robots.txt — source de signatures CMS (ex: "PrestaShop" dans le commentaire)
            robots_txt = ""
            try:
                robots_url = urljoin(url, "/robots.txt")
                robots_resp = await client.get(robots_url, headers={"User-Agent": UA})
                if robots_resp.status_code == 200:
                    robots_txt = robots_resp.text[:2000]
            except Exception:
                pass

        # Contenu combine pour les recherches
        combined_text = f"{all_headers}\n{html[:15000]}\n{robots_txt}"

        # 3. Scorer chaque CMS
        scores = {}
        for cms_name, signatures in CMS_SIGNATURES.items():
            score = 0
            found_signals = []
            for sig_type, pattern, weight in signatures:
                matched = False
                if sig_type in ("header", "html", "cookie", "meta"):
                    # Recherche dans le contenu combine (headers + HTML + robots.txt)
                    matched = bool(re.search(pattern, combined_text, re.IGNORECASE))
                elif sig_type == "file":
                    try:
                        file_url = urljoin(url, pattern.lstrip("/"))
                        file_resp = await client.head(file_url)
                        matched = file_resp.status_code == 200
                    except Exception:
                        pass
                elif sig_type == "sitemap":
                    # Chercher le pattern dans le HTML et robots.txt (pas comme URL)
                    matched = bool(re.search(pattern, combined_text, re.IGNORECASE))

                if matched:
                    score += weight
                    found_signals.append({
                        "type": sig_type,
                        "pattern": pattern[:60],
                        "weight": weight,
                    })

            if score > 0:
                scores[cms_name] = {"score": score, "signals": found_signals}

        # 4. Meilleur match
        if scores:
            best = max(scores, key=lambda k: scores[k]["score"])
            result["cms"] = best
            result["confidence"] = min(100, scores[best]["score"])
            result["signals"] = scores[best]["signals"]
            result["sitemap_candidates"] = CMS_SITEMAP_PRIORITY.get(best, [])

            # Detection version (depuis meta generator)
            v_match = re.search(
                rf'{best}\s+(\d+\.\d+(?:\.\d+)?)',
                html[:5000], re.IGNORECASE
            )
            if v_match:
                result["version"] = v_match.group(1)
            else:
                # PrestaShop: chercher dans le footer
                v_match = re.search(
                    r'(?:v|version|release)\s+(\d+\.\d+(?:\.\d+)?)',
                    html[-2000:], re.IGNORECASE
                )
                if v_match:
                    result["version"] = v_match.group(1)

    except Exception as e:
        result["error"] = str(e)

    return result


def get_cms_sitemap_hint(cms_result: dict) -> str:
    """Retourne un message utilisateur indiquant ou trouver le sitemap."""
    cms = cms_result.get("cms", "inconnu")
    candidates = cms_result.get("sitemap_candidates", [])

    hints = {
        "PrestaShop": (
            f"Site PrestaShop detecte (confiance {cms_result.get('confidence', 0)}%). "
            f"Sitemap generalement a : {candidates[0] if candidates else '/1_index_sitemap.xml'} "
            f"(visible dans robots.txt). Les URLs produit/categorie sont generees automatiquement."
        ),
        "WordPress": (
            f"Site WordPress detecte (confiance {cms_result.get('confidence', 0)}%). "
            f"Sitemap a : /wp-sitemap.xml (WordPress 5.5+). "
            f"Verifier que Yoast SEO ou RankMath ne genere pas un sitemap different."
        ),
        "Shopify": (
            f"Site Shopify detecte (confiance {cms_result.get('confidence', 0)}%). "
            f"Sitemap automatique a : /sitemap.xml. "
            f"Shopify gere automatiquement les sitemaps produits, collections et pages."
        ),
    }
    return hints.get(cms, f"CMS detecte : {cms}. Sitemap probable : {', '.join(candidates)}")
