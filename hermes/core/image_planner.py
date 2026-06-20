"""Planificateur d'images 3 niveaux — inspire de fc-solutions-ai-site.

3 images par article :
1. Hero — arriere-plan du titre (1200x630, og:image)
2. Milieu — placee entre les H2 (800x600, illustre un concept cle)
3. Infographie — synthese visuelle en fin d'article (avec logo overlay)

Le logo officiel est ajoute en overlay (jamais genere par l'IA).
"""

import re
from typing import Any, Optional


def plan_images(
    keyword: str,
    html_content: str,
    type_page: str = "article",
    company_name: str = "",
    logo_path: str = "",
) -> dict[str, Any]:
    """Planifie les 3 images editoriales pour un article.

    Args:
        keyword: mot-cle principal
        html_content: brouillon HTML
        type_page: type de page (article, service_local, etc.)
        company_name: nom de l'entreprise (pour le logo overlay)
        logo_path: chemin vers le logo officiel (pour overlay)

    Returns: {
        "hero": {...},
        "mid_content": {...},
        "infographie": {...},
        "logo_overlay": bool,
        "placement": {"hero_pos": 0, "mid_pos": 2, "infographie_pos": -1}
    }
    """
    h2_titles = _extract_h2_titles(html_content)
    h2_count = len(h2_titles)

    # Position de l'image milieu : apres le 2eme ou 3eme H2
    mid_h2_index = min(2, max(1, h2_count // 3))

    plan = {
        "hero": {
            "dimensions": "1200x630",
            "usage": "og:image + featured image",
            "alt": f"Illustration pour {keyword} — {company_name or 'article'}",
            "prompt": (
                f"Illustration professionnelle et epuree sur le theme '{keyword}'. "
                f"Style corporate moderne, couleurs sobres, espace pour texte en overlay. "
                f"Pas de texte dans l'image. Format paysage 1200x630."
            ),
            "placement": "above-the-fold",
            "preload": True,
            "lazy": False,
            "og_image": True,
        },
        "mid_content": {
            "dimensions": "800x600",
            "usage": "illustration dans le corps de l'article",
            "alt": f"Schema illustrant {h2_titles[mid_h2_index] if mid_h2_index < len(h2_titles) else keyword}",
            "prompt": (
                f"Illustration conceptuelle pour '{h2_titles[mid_h2_index] if mid_h2_index < len(h2_titles) else keyword}'. "
                f"Style editorial, couleurs en harmonie avec la marque. "
                f"Illustre un concept cle de maniere visuelle et intuitive."
            ),
            "placement": f"Apres le H2 #{mid_h2_index + 1}",
            "preload": False,
            "lazy": True,
            "og_image": False,
        },
        "infographie": {
            "dimensions": "800x1200",
            "usage": "synthese visuelle en fin d'article",
            "alt": f"Infographie recapitulative — {keyword}",
            "prompt": (
                f"Infographie synthetique sur '{keyword}'. "
                f"Style professionnel, icones, hierarchie visuelle claire. "
                f"Reserve un espace de 80px en bas pour le logo. "
                f"Texte minimal — privilegier les icones et chiffres cles."
            ),
            "placement": "Fin d'article, avant la conclusion",
            "preload": False,
            "lazy": True,
            "og_image": False,
            "logo_overlay": True,
            "logo_position": "bottom-right",
            "logo_size": "120x40",
        },
        "logo_overlay": bool(logo_path or company_name),
        "logo_info": {
            "source": logo_path or f"Logo officiel de {company_name}",
            "instruction": (
                "Le logo ne doit JAMAIS etre genere par l'IA. "
                "Il doit etre ajoute par composition depuis le fichier officiel. "
                "Position : bas-droite de l'infographie. "
                "Ne pas couvrir le contenu texte de l'infographie."
            ),
        },
        "placement": {
            "hero_pos": 0,
            "mid_pos": mid_h2_index + 1,
            "infographie_pos": -1,
        },
        "meta": {
            "total_images": 3,
            "h2_count": h2_count,
            "type_page": type_page,
        },
    }

    return plan


def _extract_h2_titles(html: str) -> list[str]:
    """Extrait les titres H2 d'un contenu HTML."""
    h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.IGNORECASE)
    return [re.sub(r"<[^>]+>", "", h).strip() for h in h2s if h.strip()]


def get_image_specs(
    plan: dict[str, Any],
    source_url: Optional[str] = None,
) -> list[dict]:
    """Convertit le plan d'images en specifications pour l'Agent 22.

    Returns: liste de dicts compatibles avec ImageSpec
    """
    specs = []
    for key in ("hero", "mid_content", "infographie"):
        img = plan.get(key, {})
        specs.append({
            "type": key,
            "dimensions": img.get("dimensions", "800x600"),
            "alt": img.get("alt", ""),
            "prompt": img.get("prompt", ""),
            "placement": img.get("placement", ""),
            "preload": img.get("preload", False),
            "lazy": img.get("lazy", True),
            "og_image": img.get("og_image", False),
            "logo_overlay": img.get("logo_overlay", False),
            "source_url": source_url,
        })
    return specs
