"""T17 — Roadmap Technique (compatible CMS).

Transforme la liste priorisee en plan d'action structure :
- Sprint 1 : Quick Wins (P0, effort < 1h)
- Sprint 2 : Corrections critiques (P0-P1)
- Sprint 3 : Optimisations (P2)
- Backlog : Chantiers structurels (P3)

Chaque recommandation indique :
- Profil cible (SEO / Dev / Hebergeur)
- Localisation CMS quand applicable
- Delai estime

$0 — deterministe.
"""

import logging
from datetime import datetime

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt17")

# Mapping categorie → profil cible
CATEGORY_PROFILE = {
    "structure": "SEO",
    "content": "SEO",
    "indexation": "SEO",
    "performance": "Developer",
    "mobile": "Developer",
    "security": "Hebergeur",
    "anomalies": "Developer",
    "architecture": "SEO",
    "maillage": "SEO",
    "international": "Developer",
    "schema": "Developer",
    "sitemap": "SEO",
    "code_quality": "Developer",
}


async def run(state: TechAuditState) -> TechAuditState:
    state.current_agent = "tt17"
    if not state.issues:
        return state

    cms = state.cms_detected or "serveur"

    roadmap = []
    sprints = {
        "Sprint 1 - Quick Wins": [],
        "Sprint 2 - Corrections critiques": [],
        "Sprint 3 - Optimisations": [],
        "Backlog - Chantiers structurels": [],
    }

    for issue in state.issues:
        target = CATEGORY_PROFILE.get(issue.category, "SEO")
        effort_min = 60
        if "5 min" in issue.effort:
            effort_min = 5
        elif "15 min" in issue.effort:
            effort_min = 15
        elif "30 min" in issue.effort:
            effort_min = 30
        elif "1h" in issue.effort:
            effort_min = 60
        elif "2h" in issue.effort:
            effort_min = 120

        # Enrichir avec la localisation CMS si pas deja fait
        cms_location = issue.cms_location
        if not cms_location and cms != "inconnu":
            cms_location = _get_cms_location(issue, cms)

        item = {
            "id": issue.id,
            "category": issue.category,
            "description": issue.description,
            "url": issue.url,
            "priority": issue.priority,
            "severity": issue.severity,
            "confidence": issue.confidence,
            "target_profile": target,
            "effort": issue.effort,
            "effort_minutes": effort_min,
            "cms_location": cms_location,
            "impact_business": issue.impact_business,
            "gain_potentiel": issue.gain_potentiel,
        }

        # Repartir dans les sprints
        if issue.priority == "P0" and effort_min <= 60:
            sprints["Sprint 1 - Quick Wins"].append(item)
        elif issue.priority in ("P0", "P1"):
            sprints["Sprint 2 - Corrections critiques"].append(item)
        elif issue.priority == "P2":
            sprints["Sprint 3 - Optimisations"].append(item)
        else:
            sprints["Backlog - Chantiers structurels"].append(item)

    # Construire la roadmap
    for sprint_name, items in sprints.items():
        if items:
            total_effort = sum(it["effort_minutes"] for it in items)
            roadmap.append({
                "sprint": sprint_name,
                "items": items,
                "count": len(items),
                "estimated_hours": round(total_effort / 60, 1),
                "targets": list(set(it["target_profile"] for it in items)),
            })

    state.roadmap = roadmap

    total_hours = sum(r["estimated_hours"] for r in roadmap)
    logger.info(f"T17: roadmap — {len(roadmap)} sprints, {sum(r['count'] for r in roadmap)} tasks, ~{total_hours}h")

    state.updated_at = datetime.now()
    return state


def _get_cms_location(issue: TechIssue, cms: str) -> str:
    """Suggere ou corriger selon le CMS."""
    if cms == "WordPress":
        locs = {
            "structure": "WordPress → Page → Yoast/ RankMath → Title & Meta",
            "content": "WordPress → Editeur → Contenu de la page",
            "indexation": "WordPress → Reglages → Lecture → Indexation",
            "performance": "WordPress → Plugins de cache (WP Rocket, W3 Total Cache)",
            "security": "WordPress → .htaccess ou plugin de securite",
            "sitemap": "WordPress → Yoast/ RankMath → Sitemap XML",
            "schema": "WordPress → Yoast/ RankMath → Schema → Type de page",
        }
        return locs.get(issue.category, "WordPress → Tableau de bord → Reglages")
    elif cms == "PrestaShop":
        locs = {
            "structure": "PrestaShop → Catalogue → Produits → Referencement",
            "content": "PrestaShop → Catalogue → Produits → Description",
            "performance": "PrestaShop → Configurer → Performances → Smarty/Cache",
            "security": "PrestaShop → .htaccess ou hebergeur",
            "sitemap": "PrestaShop → Configurer → Boutique → SEO & URLs",
            "schema": "PrestaShop → Module SEO → Structured Data",
        }
        return locs.get(issue.category)
    elif cms in ("Shopify", "Wix", "Squarespace"):
        return f"{cms} → Tableau de bord → SEO / Marketing"
    return "Serveur / CMS → Configurer manuellement"
