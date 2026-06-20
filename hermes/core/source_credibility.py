"""Classification de credibilite des sources — inspire de saas-seo et fc-solutions.

Definit 4 niveaux de credibilite (A/B/C/D) et les regles associees :
- A : Institutionnel (CNIL, ANSSI, NIST, Commission europeenne, INSEE, OMS...)
- B : Publication reconnue (Le Monde, Les Echos, Harvard Business Review...)
- C : Blog d'expert, article de recherche, rapport d'entreprise identifie
- D : Blog inconnu, forum, reseau social — INTERDIT comme source primaire
"""

import re
from typing import Optional

# Domaines de niveau A — institutionnels
TIER_A_DOMAINS: set[str] = {
    "cnil.fr", "anssi.gouv.fr", "gouvernement.fr", "service-public.fr",
    "legifrance.gouv.fr", "insee.fr", "has-sante.fr", "ameli.fr",
    "nist.gov", "europa.eu", "commission.europa.eu", "who.int",
    "banque-france.fr", "amf-france.org", "acpr.banque-france.fr",
    "ademe.fr", "afnic.fr", "arcep.fr", "autoritedelaconcurrence.fr",
    "defenseurdesdroits.fr", "senat.fr", "assemblee-nationale.fr",
}

# Domaines de niveau B — publications reconnues
TIER_B_DOMAINS: set[str] = {
    "lemonde.fr", "lesechos.fr", "lefigaro.fr", "liberation.fr",
    "lexpress.fr", "challenges.fr", "capital.fr", "latribune.fr",
    "bfmtv.com", "francetvinfo.fr", "franceinter.fr", "radiofrance.fr",
    "hbr.org", "nature.com", "science.org", "ieee.org", "arxiv.org",
    "reuters.com", "bloomberg.com", "ft.com", "wsj.com", "economist.com",
    "theguardian.com", "wired.com", "techcrunch.com", "venturebeat.com",
}

# Patterns de domaines institutionnels (regex)
TIER_A_PATTERNS: list[re.Pattern] = [
    re.compile(r"\.gouv\.fr$"),
    re.compile(r"\.gov\.[a-z]{2,3}$"),
    re.compile(r"\.edu\.[a-z]{2,3}$"),
    re.compile(r"\.int$"),
    re.compile(r"\.mil$"),
]


def classify_domain(domain: str) -> str:
    """Classe un domaine en niveau A/B/C/D.

    Returns: 'A', 'B', 'C', ou 'D'
    """
    domain = domain.lower().strip().replace("www.", "")

    if domain in TIER_A_DOMAINS or any(p.search(domain) for p in TIER_A_PATTERNS):
        return "A"
    if domain in TIER_B_DOMAINS:
        return "B"

    # Heuristiques
    if "blog" in domain or "personal" in domain or "wordpress" in domain:
        return "D"

    return "C"  # Par defaut : non classe


TIER_LABELS: dict[str, str] = {
    "A": "Institutionnel",
    "B": "Publication reconnue",
    "C": "Blog expert / source specialisee",
    "D": "Non verifiable",
}

MIN_SOURCE_TIER_BY_YMYL: dict[str, str] = {
    "droit": "A",
    "finance": "A or B",
    "sante": "A",
    "cybersecurite": "A",
    "rh": "B",
    "donnees_personnelles": "A",
    "enfants": "A",
    "vehicules": "B",
    "produits_reglementes": "A",
}

# Secteurs YMYL (Your Money Your Life)
YMYL_SECTEURS: set[str] = {
    "droit", "finance", "sante", "cybersecurite", "donnees_personnelles",
    "enfants", "vehicules", "produits_reglementes",
}


def is_ymyl_secteur(secteur: Optional[str]) -> bool:
    """Verifie si un secteur est YMYL."""
    if not secteur:
        return False
    return secteur.lower() in YMYL_SECTEURS


def get_min_source_tier(secteur: Optional[str]) -> str:
    """Retourne le niveau de source minimum pour un secteur."""
    if not secteur:
        return "C"
    return MIN_SOURCE_TIER_BY_YMYL.get(secteur.lower(), "C")


def format_source_block(sources: list[dict], secteur: Optional[str] = None) -> str:
    """Formate un bloc de sources HTML structure.

    Args:
        sources: [{"url": "...", "title": "...", "tier": "A/B/C/D", "type": "primary|secondary|context"}]
        secteur: secteur d'activite pour les exigences YMYL

    Returns: HTML string
    """
    min_tier = get_min_source_tier(secteur)
    has_primary = any(s.get("type") == "primary" for s in sources)

    lines = ['<h2>Sources</h2>', '<ul>']

    for s in sources:
        url = s.get("url", "")
        title = s.get("title", "")
        tier = s.get("tier", "C")
        stype = s.get("type", "secondary")
        label = TIER_LABELS.get(tier, "Non verifie")

        prefix = ""
        if stype == "primary":
            prefix = "📌 Source principale — "
        lines.append(
            f'<li>{prefix}<a href="{url}" rel="nofollow">{title}</a> '
            f'({label})</li>'
        )

    lines.append('</ul>')

    # Avertissement YMYL
    if secteur and is_ymyl_secteur(secteur):
        if not has_primary:
            lines.append(
                '<p><em>Note : ce sujet releve d\'un secteur reglemente. '
                'Les informations fournies sont a titre informatif et ne '
                'remplacent pas un avis professionnel.</em></p>'
            )

    return "\n".join(lines)
