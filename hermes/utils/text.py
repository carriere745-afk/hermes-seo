"""Utilitaires de texte — Flesch français, densité sémantique."""

import re
from collections import Counter


def flesch_francais(text: str) -> float:
    """Score de lisibilité Flesch adapté au français.

    Formule : 207 - (1.015 * mots_par_phrase) - (73.6 * syllabes_par_mot)

    Interprétation :
    - < 30: Très difficile
    - 30-50: Difficile
    - 50-70: Assez facile
    - > 70: Très facile
    """
    # Nettoyer
    text = text.strip()

    # Compter les phrases
    phrases = re.split(r'[.!?]+', text)
    phrases = [p.strip() for p in phrases if p.strip()]
    nb_phrases = len(phrases) or 1

    # Compter les mots
    mots = re.findall(r'\b\w+\b', text.lower())
    nb_mots = len(mots) or 1

    # Estimer les syllabes (approximation français)
    nb_syllabes = sum(_compter_syllabes(mot) for mot in mots)

    mots_par_phrase = nb_mots / nb_phrases
    syllabes_par_mot = nb_syllabes / nb_mots

    score = 207 - (1.015 * mots_par_phrase) - (73.6 * syllabes_par_mot)
    return round(max(0, min(100, score)), 1)


def _compter_syllabes(mot: str) -> int:
    """Compte approximativement les syllabes d'un mot français."""
    mot = mot.lower()
    # Compter les voyelles comme approximation
    count = len(re.findall(r'[aeiouyàâäéèêëîïôöùûüÿ]', mot))
    # Ajustements basiques
    if mot.endswith('e') and count > 1:
        count -= 1  # 'e' muet final
    return max(1, count)


def densite_semantique(text: str) -> float:
    """Entités uniques pour 1000 mots (proxy de richesse lexicale)."""
    mots = re.findall(r'\b\w{4,}\b', text.lower())
    nb_mots = len(mots) or 1
    # Mots de 4+ lettres comme proxy d'entités
    mots_riches = re.findall(r'\b\w{4,}\b', text.lower())
    uniques = len(set(mots_riches))
    return round((uniques / nb_mots) * 1000, 1)


def compter_mots(text: str) -> int:
    """Compte le nombre de mots."""
    return len(re.findall(r'\b\w+\b', text))
