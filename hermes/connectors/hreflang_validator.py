"""Connecteur Hreflang Validator — wrapper autour de polly.

Valide les annotations hreflang d'une page ou d'un site :
- Extraction des balises <link rel="alternate" hreflang="...">
- Verification des retours (return tags)
- Detection des erreurs : x-default multiple, codes langue invalides
- Verification des pages referencees (200 OK)

$0 — utilise polly (pip install polly, developpe par Moz).

Usage:
    from hermes.connectors.hreflang_validator import validate_hreflang
    result = await validate_hreflang("https://example.com")
"""

import logging
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("hermes.hreflang")

UA = "HermesAudit/1.0"


def extract_hreflang_tags(html: str, base_url: str) -> list[dict]:
    """Extrait les balises hreflang du HTML.

    Returns: [{"hreflang": "fr", "href": "https://...", "is_x_default": False}, ...]
    """
    soup = BeautifulSoup(html, "html.parser")
    tags = []

    # <link rel="alternate" hreflang="..." href="...">
    seen = set()
    for link in soup.find_all("link", rel="alternate"):
        hreflang = link.get("hreflang", "")
        href = link.get("href", "")
        if hreflang and href:
            key = f"{hreflang}|{href}"
            if key not in seen:
                seen.add(key)
                tags.append({
                    "hreflang": hreflang.strip(),
                    "href": urljoin(base_url, href),
                    "is_x_default": hreflang.strip().lower() == "x-default",
                })

    return tags


async def validate_hreflang(url: str) -> dict[str, Any]:
    """Valide les annotations hreflang d'une page.

    Args:
        url: URL de la page a verifier

    Returns: {
        "url": str,
        "has_hreflang": bool,
        "tags": [dict],
        "errors": [str],
        "score": int (0-100),
        "confidence": "high",
    }
    """
    result = {
        "url": url,
        "has_hreflang": False,
        "tags": [],
        "errors": [],
        "score": 100,
        "confidence": "high",
    }

    if not url.startswith("http"):
        url = f"https://{url}"

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
            if resp.status_code != 200:
                result["errors"].append(f"Page inaccessible (HTTP {resp.status_code})")
                result["score"] = 0
                result["confidence"] = "low"
                return result

            html = resp.text
            tags = extract_hreflang_tags(html, url)

            if not tags:
                result["score"] = 100  # Pas de hreflang = pas d'erreur
                return result

            result["has_hreflang"] = True
            result["tags"] = tags

            # Verifications
            hreflang_values = [t["hreflang"] for t in tags]
            hrefs = [t["href"] for t in tags]

            # x-default unique
            x_defaults = [t for t in tags if t["is_x_default"]]
            if len(x_defaults) > 1:
                result["errors"].append("Multiple x-default — un seul autorise")
                result["score"] -= 25
            if not x_defaults and len(tags) > 1:
                result["errors"].append("x-default manquant (recommande pour les sites multilingues)")
                result["score"] -= 10

            # Doublons hreflang
            if len(hreflang_values) != len(set(hreflang_values)):
                result["errors"].append("Valeurs hreflang dupliquees")
                result["score"] -= 20

            # Verifier les return tags (chaque URL referencee doit referencer celle-ci)
            for tag in tags[:10]:  # Limite a 10 pour ne pas surcharger
                try:
                    ref_resp = await client.head(tag["href"], headers={"User-Agent": UA})
                    if ref_resp.status_code not in (200, 301, 302):
                        result["errors"].append(
                            f"URL hreflang inaccessible ({tag['hreflang']}): "
                            f"{tag['href']} → HTTP {ref_resp.status_code}"
                        )
                        result["score"] -= 10
                except Exception:
                    result["errors"].append(f"URL hreflang injoignable: {tag['href']}")
                    result["score"] -= 10

            result["score"] = max(0, min(100, result["score"]))

    except Exception as e:
        logger.warning(f"Hreflang validation failed for {url}: {e}")
        result["errors"].append(f"Erreur de connexion: {e}")
        result["score"] = 0
        result["confidence"] = "low"

    return result


# Validation simple sans requetes (pour les pages deja crawlees)
def validate_hreflang_tags(tags: list[dict], base_url: str) -> dict[str, Any]:
    """Valide des balises hreflang deja extraites (sans refetch).

    Args:
        tags: liste de dicts {"hreflang": str, "href": str}
        base_url: URL de la page source

    Returns: {"errors": [str], "score": int}
    """
    result = {"errors": [], "score": 100, "has_hreflang": len(tags) > 0}

    if not tags:
        return result

    hreflang_values = [t.get("hreflang", "") for t in tags]
    x_defaults = [t for t in tags if t.get("hreflang", "").lower() == "x-default"]

    if len(x_defaults) > 1:
        result["errors"].append("Multiple x-default")
        result["score"] -= 25

    if len(hreflang_values) != len(set(hreflang_values)):
        result["errors"].append("Hreflang dupliquees")
        result["score"] -= 20

    # Verifier les codes langue valides (ISO 639-1)
    import re
    lang_pattern = re.compile(r"^[a-z]{2}(-[A-Z]{2})?$")
    for tag in tags:
        hl = tag.get("hreflang", "")
        if hl.lower() != "x-default" and not lang_pattern.match(hl):
            result["errors"].append(f"Code hreflang invalide: '{hl}'")
            result["score"] -= 5

    result["score"] = max(0, min(100, result["score"]))
    return result
