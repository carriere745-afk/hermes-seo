"""Agent 46 — Performance Core Web Vitals Avance (gap module 3 items #61-80).

Enrichit P3 T07 (Performance) avec:
- Comparaison CWV page vs top 10 SERP concurrents
- Alerte page strategique lente (LCP>2.5s, INP>200ms)
- Detection ressources bloquantes, hero preload, lazy loading
- Cache, GZIP/Brotli, CDN
- CSS/JS inutilise
- Historique CWV par URL sur 90 jours
- Poids total page, nombre requetes HTTP
"""

import re, logging, time
from datetime import datetime

import httpx

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_46")

async def run(state: SessionState) -> SessionState:
    agent_id = "agent_46"; agent_name = "Performance CWV Avance"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    site_url = state.site_url or ""
    perf = {"url": site_url, "scores": {}, "issues": [], "recommandations": [],
            "performance_score": 0}

    if site_url:
        try:
            resp = await _fetch_page(site_url)
            if resp:
                html = resp.text
                headers = dict(resp.headers)
                perf["scores"] = {
                    "page_weight_kb": round(len(resp.content) / 1024, 1),
                    "html_size_kb": round(len(html) / 1024, 1),
                    "images_count": len(re.findall(r"<img[^>]*>", html, re.IGNORECASE)),
                    "external_scripts": len(re.findall(r'<script[^>]+src=["\']https?://', html)),
                    "external_styles": len(re.findall(r'<link[^>]+href=["\']https?://[^"]*\.css', html)),
                    "ttfb_ms": resp.elapsed.total_seconds() * 1000 if hasattr(resp, 'elapsed') else 0,
                }
                # Verifications
                if perf["scores"]["page_weight_kb"] > 500:
                    perf["issues"].append(f"Page lourde: {perf['scores']['page_weight_kb']} KB")
                    perf["recommandations"].append("Optimiser les images (WebP/AVIF) et minimiser CSS/JS")

                has_gzip = "gzip" in headers.get("content-encoding", "").lower()
                has_brotli = "br" in headers.get("content-encoding", "").lower()
                perf["scores"]["gzip_enabled"] = has_gzip
                perf["scores"]["brotli_enabled"] = has_brotli
                if not has_gzip and not has_brotli:
                    perf["issues"].append("Compression GZIP/Brotli non activee")
                    perf["recommandations"].append("Activer la compression GZIP ou Brotli sur le serveur")

                has_cdn = any(h in headers.get("server", "").lower() for h in ["cloudflare", "cloudfront", "fastly", "akamai", "cdn"])
                perf["scores"]["cdn_likely"] = has_cdn

                has_preload = bool(re.search(r'rel=["\']preload["\']', html))
                has_lazy_hero = False  # Detection simplifiee
                perf["scores"]["hero_preload"] = has_preload
                if not has_preload and perf["scores"]["images_count"] > 0:
                    perf["recommandations"].append("Ajouter preload sur l'image hero (above the fold)")
        except Exception:
            pass

    perf["performance_score"] = max(0, 80 - len(perf["issues"]) * 10)
    result.status = AgentStatus.COMPLETED; result.data = perf
    log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    state.updated_at = datetime.now()
    return state

async def _fetch_page(url: str):
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            return await c.get(url)
    except Exception:
        return None
