"""Connecteur Security Headers — wrapper defensif autour de shcheck.

Analyse les headers HTTP de securite d'un site :
- HSTS (Strict-Transport-Security)
- CSP (Content-Security-Policy)
- X-Frame-Options
- X-Content-Type-Options
- Referrer-Policy
- Permissions-Policy
- HTTPS / certificat SSL

Defensif : uniquement des requetes HEAD/GET publiques, pas de scanning.
$0 — utilise shcheck (GPL-3.0, pip install shcheck).

Usage:
    from hermes.connectors.security_headers import check_security_headers
    result = await check_security_headers("https://example.com")
"""

import logging
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("hermes.security_headers")

UA = "HermesAudit/1.0"

# Headers de securite a verifier
SECURITY_HEADERS = {
    "strict-transport-security": {
        "name": "HSTS",
        "severity": "high",
        "recommendation": "Ajouter 'Strict-Transport-Security: max-age=31536000; includeSubDomains'",
    },
    "content-security-policy": {
        "name": "CSP",
        "severity": "medium",
        "recommendation": "Definir une Content-Security-Policy pour limiter les sources de scripts/styles",
    },
    "x-frame-options": {
        "name": "X-Frame-Options",
        "severity": "medium",
        "recommendation": "Ajouter 'X-Frame-Options: DENY' ou 'SAMEORIGIN'",
    },
    "x-content-type-options": {
        "name": "X-Content-Type-Options",
        "severity": "low",
        "recommendation": "Ajouter 'X-Content-Type-Options: nosniff'",
    },
    "referrer-policy": {
        "name": "Referrer-Policy",
        "severity": "low",
        "recommendation": "Definir 'Referrer-Policy: strict-origin-when-cross-origin'",
    },
    "permissions-policy": {
        "name": "Permissions-Policy",
        "severity": "low",
        "recommendation": "Definir une Permissions-Policy pour restreindre les API navigateur",
    },
}


async def check_security_headers(url: str) -> dict[str, Any]:
    """Analyse les headers de securite d'une URL.

    Approche defensive : HEAD request uniquement, pas de scanning.

    Args:
        url: URL du site (https://...)

    Returns: {
        "url": str,
        "is_https": bool,
        "score": int (0-100),
        "headers_found": [str],
        "headers_missing": [str],
        "issues": [{"header": str, "severity": str, "found": bool, "recommendation": str}],
        "raw_headers": dict,
    }
    """
    result = {
        "url": url,
        "is_https": url.startswith("https"),
        "score": 100,
        "headers_found": [],
        "headers_missing": [],
        "issues": [],
        "raw_headers": {},
        "confidence": "high",
    }

    if not url.startswith("http"):
        url = f"https://{url}"

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.head(url, headers={"User-Agent": UA})
            headers_lower = {k.lower(): v for k, v in resp.headers.items()}
            result["raw_headers"] = dict(resp.headers)
            result["is_https"] = str(resp.url).startswith("https")

            for header_key, info in SECURITY_HEADERS.items():
                found = header_key in headers_lower
                issue = {
                    "header": info["name"],
                    "key": header_key,
                    "severity": info["severity"],
                    "found": found,
                    "value": headers_lower.get(header_key, "") if found else "",
                    "recommendation": "" if found else info["recommendation"],
                }
                result["issues"].append(issue)
                if found:
                    result["headers_found"].append(info["name"])
                else:
                    result["headers_missing"].append(info["name"])
                    if info["severity"] == "high":
                        result["score"] -= 20
                    elif info["severity"] == "medium":
                        result["score"] -= 10
                    else:
                        result["score"] -= 5

    except Exception as e:
        logger.warning(f"Security headers check failed for {url}: {e}")
        result["score"] = 0
        result["confidence"] = "low"
        result["issues"].append({
            "header": "Connection",
            "key": "connection",
            "severity": "high",
            "found": False,
            "value": "",
            "recommendation": f"Impossible de se connecter au site : {e}",
        })

    result["score"] = max(0, min(100, result["score"]))
    return result


async def check_https_only(url: str) -> dict:
    """Verifie que HTTP redirige vers HTTPS."""
    result = {"url": url, "https_redirect": False, "https_works": False, "issues": []}

    parsed = urlparse(url if url.startswith("http") else f"https://{url}")
    domain = parsed.netloc or parsed.path.split("/")[0]
    https_url = f"https://{domain}"
    http_url = f"http://{domain}"

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            # Test HTTPS
            resp_https = await client.head(https_url, headers={"User-Agent": UA})
            result["https_works"] = resp_https.status_code < 500

            # Test HTTP → HTTPS redirect
            resp_http = await client.head(http_url, headers={"User-Agent": UA})
            if resp_http.status_code in (301, 302, 307, 308):
                location = resp_http.headers.get("location", "")
                if location.startswith("https"):
                    result["https_redirect"] = True
    except Exception as e:
        logger.debug(f"HTTPS check failed for {domain}: {e}")

    if not result["https_works"]:
        result["issues"].append({
            "header": "HTTPS",
            "severity": "critical",
            "found": False,
            "recommendation": "Installer un certificat SSL/TLS valide",
        })
    elif not result["https_redirect"]:
        result["issues"].append({
            "header": "HTTP→HTTPS Redirect",
            "severity": "high",
            "found": False,
            "recommendation": "Rediriger tout le trafic HTTP vers HTTPS (301)",
        })

    return result
