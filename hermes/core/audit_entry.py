"""Gestionnaire des 5 modes d'entree pour le Pipeline Audit de Contenu.

Modes :
1. URL unique
2. Liste d'URLs (une par ligne)
3. Sitemap XML (auto-detection + BFS)
4. Crawl intelligent (BFS depuis homepage, profondeur max)
5. Import CSV (colonne 'url')
"""

import asyncio
import csv
import io
import logging
from typing import Optional

from hermes.connectors.sitemap_parser import detect_sitemaps, parse_sitemap_recursive

logger = logging.getLogger("hermes.audit.entry")


async def resolve_entry_urls(
    mode: str,
    input_value: str = "",
    max_urls: int = 50,
    max_depth: int = 3,
) -> dict:
    """Resout les URLs a auditer selon le mode d'entree.

    Args:
        mode: 'single', 'list', 'sitemap', 'crawl', 'csv'
        input_value: donnees d'entree (URL, CSV, etc.)
        max_urls: nombre max d'URLs
        max_depth: profondeur max de crawl

    Returns: {
        "success": bool,
        "urls": list[str],
        "site_url": str,
        "meta": dict,
        "error": str | None,
        "type_distribution": dict | None,
    }
    """
    result = {
        "success": False,
        "urls": [],
        "site_url": "",
        "meta": {},
        "error": None,
        "type_distribution": None,
    }

    if not input_value or not input_value.strip():
        result["error"] = "Aucune donnee fournie."
        return result

    if mode == "single":
        url = input_value.strip()
        if not url.startswith("http"):
            url = f"https://{url}"
        result["urls"] = [url]
        result["site_url"] = url
        result["success"] = True
        result["meta"] = {"mode": "single", "total": 1}

    elif mode == "list":
        lines = [l.strip() for l in input_value.split("\n") if l.strip()]
        urls = [l for l in lines if l.startswith("http")]
        if not urls:
            result["error"] = "Aucune URL valide trouvee."
            return result
        result["urls"] = urls[:max_urls]
        result["site_url"] = urls[0]
        result["success"] = True
        result["meta"] = {"mode": "list", "total": len(result["urls"])}

    elif mode == "sitemap":
        base_url = input_value.strip()
        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"

        # Auto-detecter (avec CMS hint si echec)
        detected = await detect_sitemaps(base_url)
        if not detected["found"]:
            # Essayer de donner un indice via la detection CMS
            hint = ""
            try:
                from hermes.connectors.cms_detector import detect_cms, get_cms_sitemap_hint
                cms_data = await detect_cms(base_url)
                if cms_data.get("cms") and cms_data["cms"] != "inconnu":
                    hint = get_cms_sitemap_hint(cms_data)
            except Exception:
                pass
            result["error"] = (
                "Aucun sitemap detecte. Essayez de coller l'URL du sitemap "
                "directement (ex: https://exemple.com/sitemap.xml) "
                "ou utilisez le mode 'Liste d'URLs'."
                + (f"\n\n{hint}" if hint else "")
            )
            if hint:
                result["meta"]["cms_hint"] = hint
            return result

        urls, type_dist, meta = await parse_sitemap_recursive(
            detected["urls"],
            base_url,
            max_urls=max_urls,
        )

        if not urls:
            result["error"] = "Aucune URL exploitable dans le sitemap."
            return result

        result["urls"] = urls
        result["site_url"] = base_url
        result["type_distribution"] = type_dist
        result["meta"] = {
            **meta,
            "mode": "sitemap",
            "source": detected["source"],
        }
        result["success"] = True

    elif mode == "crawl":
        # V1 simplifiee : BFS depuis la homepage
        from hermes.connectors.sitemap_parser import crawl_from_homepage

        base_url = input_value.strip()
        if not base_url.startswith("http"):
            base_url = f"https://{base_url}"

        urls = crawl_from_homepage(base_url, max_pages=max_urls, max_depth=max_depth)
        if not urls:
            result["error"] = "Aucune page decouverte via crawl."
            return result

        result["urls"] = urls
        result["site_url"] = base_url
        result["meta"] = {"mode": "crawl", "total": len(urls), "max_depth": max_depth}
        result["success"] = True

    elif mode == "csv":
        try:
            reader = csv.DictReader(io.StringIO(input_value))
            urls = []
            for row in reader:
                url = row.get("url", "").strip()
                if url and url.startswith("http"):
                    urls.append(url)
            if not urls:
                result["error"] = "Colonne 'url' introuvable ou vide dans le CSV."
                return result
            result["urls"] = urls[:max_urls]
            result["site_url"] = urls[0]
            result["meta"] = {"mode": "csv", "total": len(result["urls"])}
            result["success"] = True
        except Exception as e:
            result["error"] = f"Erreur CSV: {e}"

    else:
        result["error"] = f"Mode inconnu: {mode}"

    return result
