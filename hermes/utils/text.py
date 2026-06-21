"""Utilitaires de texte — Lisibilite, densite semantique, extraction keywords.

Utilise textstat (1140+ stars) pour le Flesch multilingue au lieu
d'une implementation custom. YAKE pour l'extraction de mots-cles.
"""

import re
from collections import Counter


def flesch_francais(text: str) -> float:
    """Score de lisibilite Flesch adapte au francais.

    Utilise textstat (bibliotheque testee, 40+ langues, 1140+ stars GitHub).
    Fallback sur l'implementation custom si textstat echoue.

    Interpretation :
    - < 30: Tres difficile
    - 30-50: Difficile
    - 50-70: Assez facile
    - > 70: Tres facile
    """
    try:
        import textstat
        textstat.set_lang("fr")
        score = textstat.flesch_reading_ease(text)
        return round(max(0, min(100, score)), 1)
    except (ImportError, Exception):
        pass

    # Fallback : implementation custom
    phrases = re.split(r"[.!?]+", text.strip())
    phrases = [p.strip() for p in phrases if p.strip()]
    nb_phrases = len(phrases) or 1

    mots = re.findall(r"\b\w+\b", text.lower())
    nb_mots = len(mots) or 1

    nb_syllabes = sum(_compter_syllabes(mot) for mot in mots)
    mots_par_phrase = nb_mots / nb_phrases
    syllabes_par_mot = nb_syllabes / nb_mots

    score = 207 - (1.015 * mots_par_phrase) - (73.6 * syllabes_par_mot)
    return round(max(0, min(100, score)), 1)


def _compter_syllabes(mot: str) -> int:
    """Compte approximativement les syllabes d'un mot francais (fallback)."""
    mot = mot.lower()
    count = len(re.findall(r"[aeiouyàâäéèêëîïôöùûüÿ]", mot))
    if mot.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def extract_keywords(text: str, max_keywords: int = 10, language: str = "fr") -> list[str]:
    """Extrait les mots-cles d'un texte via YAKE (non supervise, multilingue).

    YAKE est utilise par defaut. KeyBERT serait plus precis mais plus lourd.
    """
    try:
        import yake
        kw_extractor = yake.KeywordExtractor(
            lan=language,
            n=3,  # n-grammes de 1 a 3 mots
            top=max_keywords,
        )
        keywords = kw_extractor.extract_keywords(text)
        return [kw[0] for kw in keywords if kw[1] > 0.01]  # kw[0]=texte, kw[1]=score
    except ImportError:
        pass

    # Fallback : TF brut
    mots = re.findall(r"\b\w{4,}\b", text.lower())
    stopwords = {
        "dans", "pour", "avec", "sur", "sont", "pas", "une", "est",
        "que", "qui", "les", "des", "aux", "ces", "son", "ses",
        "cette", "leur", "leurs", "tout", "tous", "plus", "peut",
        "fait", "faire", "etre", "avoir", "aussi", "comme", "bien",
    }
    mots = [m for m in mots if m not in stopwords]
    counter = Counter(mots)
    return [word for word, _ in counter.most_common(max_keywords)]


def densite_semantique(text: str) -> float:
    """Entites uniques pour 1000 mots (proxy de richesse lexicale)."""
    mots = re.findall(r"\b\w{4,}\b", text.lower())
    nb_mots = len(mots) or 1
    mots_riches = re.findall(r"\b\w{4,}\b", text.lower())
    uniques = len(set(mots_riches))
    return round((uniques / nb_mots) * 1000, 1)


def compter_mots(text: str) -> int:
    """Compte le nombre de mots."""
    return len(re.findall(r"\b\w+\b", text))
