"""Connecteur PageSpeed Insights — Core Web Vitals.

Deux sources :
1. PageSpeed Insights API (gratuit, quotas generoux, pas de cle requise)
   -> donnees terrain CrUX + lab Lighthouse
2. Fallback heuristique (taille de page + temps de chargement)
   -> estimation approximative

$0 — pas de LLM. httpx direct.
"""

import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger("hermes.pagespeed")

# URL de l'API PageSpeed Insights v5
PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


async def analyze_page(url: str, strategy: str = "mobile") -> dict[str, Any]:
    """Analyse une page via PageSpeed Insights API.

    Args:
        url: URL a analyser
        strategy: "mobile" ou "desktop"

    Returns: {
        "source": "pagespeed_insights",
        "confidence": "high" | "medium",
        "performance_score": int (0-100),
        "lcp": {"value": ms, "label": "good"|"needs improvement"|"poor"},
        "cls": {"value": float, "label": "good"|"needs improvement"|"poor"},
        "inp": {"value": ms, "label": "good"|"needs improvement"|"poor"},
        "fcp": {"value": ms},
        "ttfb": {"value": ms},
        "speed_index": {"value": ms},
        "total_blocking_time": {"value": ms},
        "cumulative_layout_shift": {"value": float},
        "is_crux_data": bool,
        "lab_data_only": bool,
        "error": str | None,
    }
    """
    result = {
        "source": "pagespeed_insights",
        "confidence": "medium",
        "performance_score": 0,
        "lcp": {"value": 0, "label": "unknown"},
        "cls": {"value": 0.0, "label": "unknown"},
        "fcp": {"value": 0},
        "ttfb": {"value": 0},
        "speed_index": {"value": 0},
        "total_blocking_time": {"value": 0},
        "cumulative_layout_shift": {"value": 0.0},
        "is_crux_data": False,
        "lab_data_only": True,
        "error": None,
    }

    if not url.startswith("http"):
        url = f"https://{url}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                PSI_URL,
                params={
                    "url": url,
                    "strategy": strategy,
                    "category": "performance",
                },
                headers={"User-Agent": "HermesAudit/1.0"},
            )

            if resp.status_code != 200:
                result["error"] = f"PSI API HTTP {resp.status_code}"
                logger.warning(f"PageSpeed Insights failed: HTTP {resp.status_code}")
                return result

            data = resp.json()

            # Lighthouse score
            lighthouse = data.get("lighthouseResult", {})
            cats = lighthouse.get("categories", {})
            perf_cat = cats.get("performance", {})
            result["performance_score"] = int(perf_cat.get("score", 0) * 100)

            # Core Web Vitals from CrUX (field data)
            crux = data.get("loadingExperience", {})
            if crux and crux.get("metrics"):
                result["is_crux_data"] = True
                result["confidence"] = "high"
                metrics = crux["metrics"]

                if "LARGEST_CONTENTFUL_PAINT_MS" in metrics:
                    lcp = metrics["LARGEST_CONTENTFUL_PAINT_MS"]
                    result["lcp"] = {
                        "value": lcp.get("percentile", 0),
                        "label": _label_cwv("lcp", lcp.get("percentile", 0)),
                    }

                if "CUMULATIVE_LAYOUT_SHIFT_SCORE" in metrics:
                    cls = metrics["CUMULATIVE_LAYOUT_SHIFT_SCORE"]
                    result["cls"] = {
                        "value": round(cls.get("percentile", 0) / 100, 4),
                        "label": _label_cwv("cls", cls.get("percentile", 0) / 100),
                    }

            # Lighthouse lab data (always present if audit succeeded)
            audits = lighthouse.get("audits", {})
            if audits:
                lcp_audit = audits.get("largest-contentful-paint", {})
                if lcp_audit and not result["lcp"]["value"]:
                    result["lcp"] = {
                        "value": int(lcp_audit.get("numericValue", 0) or 0),
                        "label": _label_cwv("lcp", int(lcp_audit.get("numericValue", 0) or 0)),
                    }

                cls_audit = audits.get("cumulative-layout-shift", {})
                if cls_audit:
                    cls_val = round((cls_audit.get("numericValue", 0) or 0), 4)
                    if not result["cls"]["value"]:
                        result["cls"] = {
                            "value": cls_val,
                            "label": _label_cwv("cls", cls_val),
                        }

                fcp_audit = audits.get("first-contentful-paint", {})
                if fcp_audit:
                    result["fcp"]["value"] = int(fcp_audit.get("numericValue", 0) or 0)

                si_audit = audits.get("speed-index", {})
                if si_audit:
                    result["speed_index"]["value"] = int(si_audit.get("numericValue", 0) or 0)

                tbt_audit = audits.get("total-blocking-time", {})
                if tbt_audit:
                    result["total_blocking_time"]["value"] = int(tbt_audit.get("numericValue", 0) or 0)

            result["lab_data_only"] = not result["is_crux_data"]

    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"PageSpeed Insights error: {e}")

    return result


def _label_cwv(metric: str, value: float) -> str:
    """Classe une valeur CWV en good/needs improvement/poor."""
    thresholds = {
        "lcp": (2500, 4000),   # ms, good < 2500, poor > 4000
        "cls": (0.1, 0.25),
        "fid": (100, 300),
        "inp": (200, 500),
    }
    lo, hi = thresholds.get(metric, (100, 300))
    if value <= lo:
        return "good"
    elif value <= hi:
        return "needs improvement"
    return "poor"


def estimate_cwv_heuristic(page_size_kb: float, ttfb_ms: int, load_time_ms: int,
                           images_count: int, external_resources: int) -> dict:
    """Estime les CWV de maniere heuristique (fallback sans PSI).

    Tres approximatif — confidence "low".
    """
    lcp_est = 0
    cls_est = 0.0
    confidence = "low"

    # LCP ~ TTFB + temps de telechargement du plus gros element
    # On estime que le plus gros element fait ~20% de la page
    lcp_est = ttfb_ms + int(page_size_kb * 0.2 / 10) * 100  # grossier

    # CLS estime (beaucoup d'images sans dimensions = risque)
    if images_count > 10 and images_count > 0:
        cls_est = 0.05 + (images_count / 100.0)
    else:
        cls_est = 0.02

    # INP ~ TBT (total blocking time) estime
    inp_est = int(load_time_ms * 0.3) if load_time_ms > 0 else 100

    return {
        "source": "heuristic",
        "confidence": confidence,
        "performance_score": max(0, 100 - int(page_size_kb / 10) - int(load_time_ms / 100)),
        "lcp": {"value": lcp_est, "label": _label_cwv("lcp", lcp_est)},
        "cls": {"value": cls_est, "label": _label_cwv("cls", cls_est)},
        "fcp": {"value": int(ttfb_ms * 1.5)},
        "ttfb": {"value": ttfb_ms},
        "is_crux_data": False,
        "lab_data_only": False,
        "heuristic": True,
    }
