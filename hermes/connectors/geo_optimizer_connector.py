"""Connecteur geo-optimizer-skill — AEO/GEO Audit.

Wrappe l'audit AEO/GEO de geo-optimizer-skill (47 methodes, Princeton KDD 2024,
AutoGEO ICLR 2026). Score 0-100, band (A-F), sub-scores:
- robots.txt: 27 AI bots checked
- llms.txt: presence, sections, structure
- schema: JSON-LD, WebSite, Organization, FAQPage
- meta: title, description, OG, canonical
- content: citability, statistics, FAQs, BLUF structure

Install: pip install geo-optimizer-skill
$0 — pas de LLM, pas d'API.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger("hermes.geo_optimizer")


async def audit_aeo_geo(url: str) -> dict[str, Any]:
    """Execute un audit AEO/GEO complet via geo-optimizer-skill.

    Args:
        url: URL du site (https://...)

    Returns: {
        "score": int (0-100),
        "band": str ("A" a "F"),
        "robots_score": int,
        "llms_txt_score": int,
        "schema_score": int,
        "meta_score": int,
        "content_score": int,
        "issues": [str],
        "recommendations": [str],
        "error": str | None,
    }
    """
    result = {
        "score": 0,
        "band": "F",
        "robots_score": 0,
        "llms_txt_score": 0,
        "schema_score": 0,
        "meta_score": 0,
        "content_score": 0,
        "issues": [],
        "recommendations": [],
        "error": None,
    }

    try:
        from geo_optimizer import audit

        audit_result = audit(url, use_cache=True)
        if audit_result is None:
            result["error"] = "geo-optimizer returned None"
            return result

        result["score"] = getattr(audit_result, "score", 0) or 0
        result["band"] = getattr(audit_result, "band", "?") or "?"

        # Sub-scores
        for sub_name in ("robots", "llms_txt", "schema", "meta", "content"):
            sub = getattr(audit_result, sub_name, None)
            if sub is not None:
                sub_score = getattr(sub, "score", 0) or 0
                result[f"{sub_name}_score"] = sub_score

                # Issues
                sub_issues = getattr(sub, "issues", []) or []
                for iss in sub_issues[:3]:
                    result["issues"].append(str(iss))

        # Recommendations
        recos = getattr(audit_result, "recommendations", []) or []
        result["recommendations"] = [str(r) for r in recos[:5]]

        logger.info(f"GEO Optimizer: {url} -> score={result['score']}/100, band={result['band']}")

    except ImportError:
        result["error"] = "geo-optimizer-skill not installed (pip install geo-optimizer-skill)"
        logger.debug(result["error"])
    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"GEO Optimizer audit failed: {e}")

    return result
