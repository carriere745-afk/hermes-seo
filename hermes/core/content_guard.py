"""Garde-fous enrichis pre-publication — portage depuis saas-seo et fc-solutions.

Inspire de :
- saas-seo/lib/llm-guard.js (268 lignes) — anti-hallucination, pageTypeAwareGuard
- fc-solutions-ai-site — checklist 60+ points, detection contenu interne expose
"""

import re


# Patterns de contenu interne qui ne doivent JAMAIS etre visibles publiquement
INTERNAL_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)position\s*0", "Position 0"),
    (r"(?i)\bRAG\b", "RAG"),
    (r"(?i)ce\s+brouillon", "ce brouillon"),
    (r"(?i)avant\s+publication", "avant publication"),
    (r"(?i)sources?\s*a\s*verifier", "sources a verifier"),
    (r"(?i)\bprompt\b.*\b(pipeline|interne|systeme|consigne)\b", "prompt/pipeline"),
    (r"(?i)scores?\s*(internes?|SEO|AEO|GEO)", "scores internes"),
    (r"(?i)justification\s*(interne|agent)", "justification interne"),
    (r"(?i)\b(brouillon|draft)\b.*\b(a\s*ameliorer|a\s*corriger|non\s*relu)\b", "annotation brouillon"),
    (r"(?i)\[RAG\]|<<RAG>>|\{RAG\}", "marqueur RAG"),
    (r"(?i)\[SOURCE\]|<<SOURCE>>", "marqueur source"),
    (r"(?i)\bTODO\b.*\b(verifier|corriger|ajouter|supprimer)\b", "TODO interne"),
    (r"(?i)\bFIXME\b", "FIXME"),
]

# Affirmations fortes sans source (pattern detection, pas LLM)
UNSOURCED_CLAIM_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)(le\s+)?(meilleur|premier|seul|unique|leader|numero\s*1|n°\s*1)\s+(de|du|des|en|sur|au)", re.IGNORECASE),
    re.compile(r"(?i)\+\s*de\s*\d{1,3}\s*(%|pour\s*cent|millions?|milliards?)", re.IGNORECASE),
    re.compile(r"(?i)\d+\s*(fois|x)\s*plus\s*(rapide|efficace|performant|puissant)", re.IGNORECASE),
    re.compile(r"(?i)(tous|la\s*plupart|chaque|aucun|personne\s*ne)\s+(les?\s+)?(clients?|utilisateurs?|entreprises?)", re.IGNORECASE),
    re.compile(r"(?i)revolutionnaire|redefinition|game.?changer|disruptif", re.IGNORECASE),
]

# Liste des formulations generiques interdites (placeholder)
PLACEHOLDER_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?i)contenu\s+detail+le\s+sur", re.IGNORECASE),
    re.compile(r"(?i)cette\s+section\s+couvre\s+les\s+points\s+essentiels", re.IGNORECASE),
    re.compile(r"(?i)decouvrez\s+tout\s+sur\s+\w+", re.IGNORECASE),
    re.compile(r"(?i)informations?\s+verifi(c|qu)ables?\s+et\s+exemples?\s+concrets?", re.IGNORECASE),
    re.compile(r"(?i)nous\s+aborderons\s+tous\s+les\s+aspects", re.IGNORECASE),
    re.compile(r"(?i)que\s+vous\s+soyez\s+debutant\s+ou\s+expert", re.IGNORECASE),
]

# Garde-fous structurels par type de page
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "article": ["h1", "intro", "conclusion"],
    "pilier": ["h1", "intro", "faq", "conclusion", "sources"],
    "service_local": ["h1", "intro", "services", "cta"],
    "comparatif": ["h1", "intro", "tableau", "verdict"],
    "landing": ["h1", "promesse", "cta"],
    "fiche_produit": ["h1", "caracteristiques", "prix"],
    "faq": ["h1", "faq"],
    "news": ["h1", "date", "source"],
    "glossaire": ["h1", "definition"],
    "temoignage": ["h1", "histoire", "resultats"],
}


def check_internal_content(html: str) -> list[dict]:
    """Detecte les patterns de contenu interne exposes publiquement.

    Returns: [{"pattern": "Position 0", "match": "Position 0 : ...", "category": "interne"}]
    """
    findings = []
    for pattern, label in INTERNAL_PATTERNS:
        matches = list(re.finditer(pattern, html))
        for m in matches:
            context = html[max(0, m.start() - 20):m.end() + 30]
            findings.append({
                "pattern": label,
                "match": context.strip(),
                "position": m.start(),
                "category": "contenu_interne",
            })
    return findings


def check_unsourced_claims(html: str) -> list[dict]:
    """Detecte les affirmations fortes sans source proche.

    Returns: [{"pattern": "meilleur de...", "match": "...", "category": "claim_non_source"}]
    """
    findings = []
    for pattern in UNSOURCED_CLAIM_PATTERNS:
        for m in pattern.finditer(html):
            # Verifier s'il y a une source dans les 100 caracteres suivants
            after = html[m.end():m.end() + 150]
            has_source = bool(re.search(r"(?i)(selon|d'apres|source|etude|rapport|INSEE|CNIL|ANSSI|Wikipedia)", after))
            findings.append({
                "pattern": m.group(),
                "match": html[max(0, m.start() - 10):m.end() + 40].strip(),
                "has_source_nearby": has_source,
                "category": "claim_non_source" if not has_source else "claim_sourcee",
            })
    return findings


def check_placeholders(html: str) -> list[dict]:
    """Detecte les formulations generiques placeholder.

    Returns: [{"pattern": "contenu detaille sur", "match": "...", "category": "placeholder"}]
    """
    findings = []
    for pattern in PLACEHOLDER_PATTERNS:
        for m in pattern.finditer(html):
            findings.append({
                "pattern": m.group()[:80],
                "match": html[max(0, m.start() - 5):m.end() + 5].strip(),
                "category": "placeholder",
            })
    return findings


def check_structure(html: str, type_page: str) -> dict:
    """Verifie la structure obligatoire selon le type de page.

    Returns: {"passed": bool, "missing": [...], "warnings": [...]}
    """
    required = REQUIRED_SECTIONS.get(type_page, ["h1", "intro"])
    missing = []
    warnings = []

    html_lower = html.lower()

    if "h1" in required and "<h1" not in html_lower:
        missing.append("H1 absent")
    if "intro" in required:
        # Intro : >= 80 mots avant le premier H2
        h2_pos = html_lower.find("<h2")
        if h2_pos > 0:
            intro_text = html[:h2_pos]
            intro_words = len(re.findall(r"\b\w+\b", intro_text))
            if intro_words < 50:
                warnings.append(f"Introduction courte ({intro_words} mots, min 50)")
        else:
            missing.append("Pas de H2 detecte — structure plate")

    if "faq" in required and "<h2" not in html_lower:
        # Verifier la presence d'un bloc FAQ
        has_faq = bool(re.search(r"(?i)(faq|questions?\s*frequentes?|questions?\s*réponses?)", html))
        if not has_faq:
            missing.append("FAQ absente (obligatoire pour ce type)")

    if "tableau" in required and "<table" not in html_lower:
        warnings.append("Tableau comparatif absent (recommande)")

    if "sources" in required:
        has_sources = bool(re.search(r"(?i)(sources?|references?|bibliographie)", html[-500:]))
        if not has_sources:
            warnings.append("Bloc sources absent en fin d'article")

    if "date" in required:
        has_date = bool(re.search(r"\b\d{1,2}\s+(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\s+\d{4}\b", html_lower))
        if not has_date:
            warnings.append("Date non trouvee dans le contenu")

    if "cta" in required:
        has_cta = bool(re.search(r"(?i)(contactez|appelez|devis|demandez|rendez.vous|gratuit)", html[-300:]))
        if not has_cta:
            warnings.append("CTA absent en fin d'article")

    return {
        "passed": len(missing) == 0,
        "missing": missing,
        "warnings": warnings,
    }


def run_quality_checks(html: str, type_page: str = "article") -> dict:
    """Execute tous les garde-fous qualite pre-publication.

    Returns un dict avec le resume de tous les checks.
    """
    internal = check_internal_content(html)
    claims = check_unsourced_claims(html)
    placeholders = check_placeholders(html)
    structure = check_structure(html, type_page)

    blocking = []
    if internal:
        blocking.append(f"Contenu interne expose : {len(internal)} occurrence(s)")
    if placeholders:
        blocking.append(f"Placeholders generiques : {len(placeholders)} occurrence(s)")
    if not structure["passed"]:
        blocking.append(f"Structure manquante : {', '.join(structure['missing'])}")

    unsourced_claims = [c for c in claims if c["category"] == "claim_non_source"]

    return {
        "passed": len(blocking) == 0,
        "blocking": blocking,
        "warnings": structure["warnings"],
        "internal_content": internal,
        "unsourced_claims": unsourced_claims,
        "placeholders": placeholders,
        "structure": structure,
    }
