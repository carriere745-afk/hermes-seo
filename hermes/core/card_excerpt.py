"""Generateur d'extraits de cartes optimises clic.

Inspire de fc-solutions-ai-site/smartSnippet() et fc_ai_card_excerpt().
Produit des snippets courts, complets et accrocheurs pour les listings.
"""

import re


def generate_card_excerpt(html: str, max_chars: int = 160) -> str:
    """Genere un extrait de carte optimise pour le clic.

    Regles :
    - Phrase complete (pas de coupure en milieu de phrase)
    - Ne finit pas sur un mot coupe
    - Ne reprend pas le bloc "En bref" tel quel
    - Donne envie de cliquer
    - Fidele au contenu

    Args:
        html: contenu HTML de l'article
        max_chars: longueur maximale en caracteres

    Returns: extrait texte pret a l'affichage
    """
    # Extraire le texte sans les balises
    text = _strip_html(html)

    # Supprimer le H1 (premiere ligne souvent)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if lines:
        # Sauter la premiere ligne si elle ressemble a un titre
        if len(lines[0]) < 120 and lines[0].istitle():
            lines = lines[1:]

    body = " ".join(lines)

    # Supprimer les patterns internes
    body = re.sub(r"Contenu detaille sur .*?\.", "", body)
    body = re.sub(r"Cette section couvre les points essentiels.*?\.", "", body)
    body = re.sub(r"En bref\s*[:\-]?\s*", "", body, flags=re.IGNORECASE)

    # Normaliser les espaces
    body = re.sub(r"\s+", " ", body).strip()

    if len(body) <= max_chars:
        return _ensure_complete_sentence(body)

    # Couper a max_chars puis revenir au dernier point
    truncated = body[:max_chars]
    last_period = truncated.rfind(".")
    last_excl = truncated.rfind("!")
    last_question = truncated.rfind("?")

    cut_point = max(last_period, last_excl, last_question)
    if cut_point > max_chars * 0.5:  # Au moins la moitie de la longueur
        return truncated[:cut_point + 1].strip()
    else:
        # Pas de ponctuation proche, couper au dernier espace
        last_space = truncated.rfind(" ")
        if last_space > max_chars * 0.7:
            return truncated[:last_space].strip() + "..."
        return truncated.strip() + "..."


def _strip_html(html: str) -> str:
    """Supprime les balises HTML basiquement."""
    # Remplacer les balises de bloc par des sauts de ligne
    for tag in ("h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "li", "br"):
        html = re.sub(rf"<\s*{tag}[^>]*>", "\n", html, flags=re.IGNORECASE)
        html = re.sub(rf"<\s*/\s*{tag}\s*>", "\n", html, flags=re.IGNORECASE)

    # Supprimer toutes les balises restantes
    html = re.sub(r"<[^>]+>", "", html)

    # Decoder les entites HTML courantes
    html = html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    html = html.replace("&nbsp;", " ").replace("&laquo;", "«").replace("&raquo;", "»")
    html = html.replace("&#8217;", "'").replace("&#8211;", "–").replace("&quot;", '"')

    return html


def _ensure_complete_sentence(text: str) -> str:
    """S'assure que le texte finit par une phrase complete."""
    if not text:
        return text
    if text[-1] in ".!?":
        return text
    # Chercher le dernier point
    last_period = max(text.rfind("."), text.rfind("!"), text.rfind("?"))
    if last_period > len(text) * 0.5:
        return text[:last_period + 1].strip()
    return text.strip() + "."
