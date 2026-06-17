"""Guardrails — Protection contre les injections et abus.

Applique aux frontieres utilisateur (keyword, objectif, site_url)
pour empecher les prompts malveillants d'atteindre les LLMs.
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# Patterns d'injection prompt connus (multi-langue)
INJECTION_PATTERNS: list[re.Pattern] = [
    # Ordres directs a l'IA
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompts?|rules?)", re.IGNORECASE),
    re.compile(r"oublie?\s+(toutes?\s+)?(les?\s+)?(consignes?|instructions?|regles?)", re.IGNORECASE),
    re.compile(r"oublie\s+tout\s+(ce\s+qui\s+precede|et\s+(ecris?|fais?|reponds?|genere?|redige?|cree?))", re.IGNORECASE),
    re.compile(r"(ne\s+)?(suis|respecte|applique)\s+pas\s+(les|mes|tes)", re.IGNORECASE),
    re.compile(r"(do\s+)?not\s+(follow|obey|listen|comply)", re.IGNORECASE),
    # Reinitialisation et detournement
    re.compile(r"(reset|reinitialise?|restart|reload)\s+(your|ton|vos)\s+(state|etat|context)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(a\s+)?(different|new|another)", re.IGNORECASE),
    re.compile(r"tu\s+es\s+(maintenant|desormais|a\s+present)\s+(un|une)\s+(nouveau|nouvelle|different)", re.IGNORECASE),
    re.compile(r"(act|behave|pretend|pose|fais\s+semblant|joue\s+le\s+role)\s+(as|like|comme|d')", re.IGNORECASE),
    # Tentatives de jailbreak
    re.compile(r"(jailbreak|dan\b|roleplay|system\s*prompt)", re.IGNORECASE),
    re.compile(r"(bypass|override|evade|circumvent|contourne)", re.IGNORECASE),
    re.compile(r"(disable|turn\s*off|desactive)\s+(safety|security|filter|guard)", re.IGNORECASE),
    # Delimiteurs d'injection
    re.compile(r"<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\]|<<SYS>>|<</SYS>>"),
    re.compile(r"<system>|</system>|<user>|</user>|<assistant>|</assistant>"),
    re.compile(r"\[system\]|\[/system\]|\[user\]|\[/user\]|\[assistant\]|\[/assistant\]"),
    # Tentatives d'execution de code
    re.compile(r"import\s+(os|subprocess|sys|shutil|socket|requests|urllib)", re.IGNORECASE),
    re.compile(r"(exec|eval|system|popen|spawn|fork)\s*\(", re.IGNORECASE),
    re.compile(r"__import__|__builtins__|__subclasses__", re.IGNORECASE),
    # Exfiltration / URLs suspectes
    re.compile(r"(curl|wget|fetch|webhook)\s.*(http|https)", re.IGNORECASE),
    re.compile(r"send\s+(this|the\s+(result|output|content))\s+to", re.IGNORECASE),
]

# Mots-cles interdits (contenu illegal, dangereux, hors charte)
BLOCKED_KEYWORDS: list[re.Pattern] = [
    re.compile(r"\b(malware|ransomware|phishing|piratage|hacking|crack)\b", re.IGNORECASE),
    re.compile(r"\b(exploit|vulnerability|zero[-\s]day|backdoor)\b", re.IGNORECASE),
    re.compile(r"\b(weapon|explosive|bomb|anthrax|poison|bioweapon)\b", re.IGNORECASE),
    re.compile(r"\b(child\s*(porn|abuse|exploitation)|pedophil|grooming)\b", re.IGNORECASE),
    re.compile(r"\b(human\s*trafficking|organ\s*harvesting|snuff)\b", re.IGNORECASE),
    re.compile(r"\b(drug\s*(trafficking|manufacturing|cooking)|meth\s*lab)\b", re.IGNORECASE),
    re.compile(r"\b(suicide\s*method|how\s*to\s*(kill|murder|assassinate))\b", re.IGNORECASE),
    re.compile(r"\b(terroris[tm]?|extremis[tm]?|radicali[sz]ation)\b", re.IGNORECASE),
    re.compile(r"\b(hate\s*speech|incels?\b|white\s*supremac)\b", re.IGNORECASE),
    re.compile(r"\b(deepfake|revenge\s*porn|non[-\s]consensual)\b", re.IGNORECASE),
]

# Limites de longueur
MAX_KEYWORD_LENGTH = 200
MAX_OBJECTIF_LENGTH = 500
MAX_URL_LENGTH = 500


@dataclass
class GuardResult:
    """Resultat d'une verification guardrail."""
    passed: bool
    reason: str = ""
    matched_pattern: str = ""
    category: str = ""  # injection, blocked_keyword, length, url


def sanitize_input(text: str, max_length: int = MAX_KEYWORD_LENGTH) -> str:
    """Nettoie un input utilisateur : strip, tronque, normalise."""
    if not text:
        return ""
    # Nettoyer les caracteres de controle sauf saut de ligne
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    # Normaliser les espaces
    text = " ".join(text.split())
    return text[:max_length]


def check_prompt_injection(text: str) -> GuardResult:
    """Verifie si un texte contient une tentative d'injection de prompt."""
    for pattern in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return GuardResult(
                passed=False,
                reason=f"Injection de prompt detectee: '{match.group()}'",
                matched_pattern=match.group(),
                category="injection",
            )
    return GuardResult(passed=True)


def check_blocked_keywords(text: str) -> GuardResult:
    """Verifie si un texte contient des mots-cles bloques."""
    for pattern in BLOCKED_KEYWORDS:
        match = pattern.search(text)
        if match:
            return GuardResult(
                passed=False,
                reason="Contenu non autorise (hors charte securite)",
                matched_pattern=match.group(),
                category="blocked_keyword",
            )
    return GuardResult(passed=True)


def validate_keyword(keyword: str) -> GuardResult:
    """Validation complete d'un mot-cle utilisateur."""
    if not keyword or not keyword.strip():
        return GuardResult(passed=False, reason="Mot-cle vide", category="length")

    keyword = keyword.strip()

    if len(keyword) > MAX_KEYWORD_LENGTH:
        return GuardResult(
            passed=False,
            reason=f"Mot-cle trop long ({len(keyword)} caracteres, max {MAX_KEYWORD_LENGTH})",
            category="length",
        )

    # Check injection
    result = check_prompt_injection(keyword)
    if not result.passed:
        return result

    # Check mots bloques
    result = check_blocked_keywords(keyword)
    if not result.passed:
        return result

    return GuardResult(passed=True)


def validate_objectif(objectif: str) -> GuardResult:
    """Validation d'un objectif utilisateur."""
    if not objectif or not objectif.strip():
        return GuardResult(passed=True)  # Optionnel

    objectif = objectif.strip()

    if len(objectif) > MAX_OBJECTIF_LENGTH:
        return GuardResult(
            passed=False,
            reason=f"Objectif trop long ({len(objectif)} caracteres, max {MAX_OBJECTIF_LENGTH})",
            category="length",
        )

    result = check_prompt_injection(objectif)
    if not result.passed:
        return result

    result = check_blocked_keywords(objectif)
    if not result.passed:
        return result

    return GuardResult(passed=True)


def validate_url(url: str) -> GuardResult:
    """Validation d'une URL."""
    if not url or not url.strip():
        return GuardResult(passed=True)  # Optionnel

    url = url.strip()

    if len(url) > MAX_URL_LENGTH:
        return GuardResult(
            passed=False,
            reason=f"URL trop longue ({len(url)} caracteres)",
            category="length",
        )

    # Verifier que c'est une URL valide
    if not re.match(r"^https?://[^\s]+$", url, re.IGNORECASE):
        return GuardResult(
            passed=False,
            reason="Format d'URL invalide (doit commencer par http:// ou https://)",
            category="url",
        )

    # Verifier que l'URL ne contient pas d'injection
    result = check_prompt_injection(url)
    if not result.passed:
        return result

    return GuardResult(passed=True)
