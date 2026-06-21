"""Scraper de site web — extraction automatique d'informations entreprise.

Utilise par l'Agent 01 en mode "brief minimal" : si l'utilisateur
ne fournit qu'un mot-cle sans details, le scraper va chercher
automatiquement les infos sur le site de l'entreprise.
"""

import re
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


async def scrape_site_summary(url: str, timeout: int = 15) -> dict[str, Any]:
    """Scrape un site web et extrait un resume structure.

    Args:
        url: URL du site (https://...)
        timeout: timeout HTTP en secondes

    Returns: {
        "nom": "Nom trouve",
        "description": "Description trouvee",
        "secteur_detecte": "secteur probable",
        "ton_detecte": "ton probable",
        "services": ["service 1", "service 2"],
        "contact": {"email": "...", "telephone": "...", "adresse": "..."},
        "reseaux_sociaux": ["https://linkedin.com/..."],
        "pages_cles": ["/a-propos", "/services", "/contact"],
        "mots_cles_site": ["mot1", "mot2"],
        "contenu_page_accueil": "extrait texte (500 car.)",
        "erreur": None,
    }
    """
    result = {
        "nom": "",
        "description": "",
        "secteur_detecte": "",
        "ton_detecte": "professionnel",
        "services": [],
        "contact": {},
        "reseaux_sociaux": [],
        "pages_cles": [],
        "mots_cles_site": [],
        "contenu_page_accueil": "",
        "erreur": None,
    }

    if not url or not url.startswith("http"):
        result["erreur"] = "URL invalide"
        return result

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "HermesSEO/3.0"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:
        result["erreur"] = f"Echec fetch: {e}"
        return result

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        result["erreur"] = f"Echec parse: {e}"
        return result

    # Nom du site
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        # Nettoyer : enlever "| NomSite", "- NomSite", "— NomSite"
        result["nom"] = re.split(r"\s*[|—\-]\s*", title)[-1].strip()

    # Meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc:
        result["description"] = meta_desc.get("content", "")[:300]

    # Services / offres (depuis les H2, H3, ou une section "services")
    for tag in soup.find_all(["h2", "h3"]):
        text = tag.get_text(strip=True).lower()
        if any(w in text for w in ("service", "prestation", "offre", "produit", "solution")):
            parent = tag.find_parent()
            if parent:
                items = parent.find_all("li")
                for li in items[:10]:
                    t = li.get_text(strip=True)
                    if len(t) > 10:
                        result["services"].append(t[:100])

    # Sans services trouves, chercher dans les H2
    if not result["services"]:
        for h2 in soup.find_all("h2")[:10]:
            text = h2.get_text(strip=True)
            if len(text) > 10 and len(text) < 120:
                result["services"].append(text)

    # Contact
    body = soup.get_text()
    email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", body)
    if email_match:
        result["contact"]["email"] = email_match.group()
    phone_match = re.search(r"(\+33|0)\s*\d[\d\s\.\-]{8,}", body)
    if phone_match:
        result["contact"]["telephone"] = phone_match.group().strip()
    address_tag = soup.find("address")
    if address_tag:
        result["contact"]["adresse"] = address_tag.get_text(strip=True)[:200]

    # Reseaux sociaux
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if any(s in href for s in ("linkedin.com/company", "twitter.com/", "facebook.com/", "instagram.com/")):
            if href not in result["reseaux_sociaux"]:
                result["reseaux_sociaux"].append(href)

    # Pages cles
    for link in soup.find_all("a", href=True):
        href = link["href"]
        text = link.get_text(strip=True).lower()
        if any(w in text for w in ("a propos", "qui sommes", "services", "contact", "blog", "realisations")):
            full_url = urljoin(url, href)
            if full_url not in result["pages_cles"]:
                result["pages_cles"].append(full_url)

    # Mots-cles du site (TF brut sur le texte visible)
    visible_text = soup.get_text(separator=" ", strip=True)
    words = re.findall(r"\b\w{4,}\b", visible_text.lower())
    stopwords = {
        "dans", "pour", "avec", "sur", "sont", "pas", "une", "est", "que", "qui",
        "les", "des", "aux", "ces", "son", "ses", "cette", "leur", "leurs",
        "tout", "tous", "plus", "peut", "fait", "faire", "etre", "avoir", "aussi",
        "comme", "bien", "entre", "nous", "vous", "nos", "vos", "cela", "dont",
    }
    words = [w for w in words if w not in stopwords]
    from collections import Counter
    result["mots_cles_site"] = [w for w, _ in Counter(words).most_common(20)]

    # Contenu page d'accueil (debut)
    result["contenu_page_accueil"] = visible_text[:500]

    # Detection du secteur
    secteur_keywords = {
        "finance": ("assurance", "banque", "credit", "placement", "investissement"),
        "sante": ("medecin", "sante", "medical", "patient", "soin"),
        "droit": ("avocat", "juridique", "droit", "justice", "notaire"),
        "ecommerce": ("boutique", "achat", "livraison", "commande", "panier"),
        "saas": ("logiciel", "api", "cloud", "demo", "essai gratuit"),
        "formation": ("formation", "cours", "apprendre", "certification"),
        "immobilier": ("immobilier", "achat", "location", "vente", "appartement"),
        "tourisme": ("hotel", "visite", "sejour", "tourisme", "reservation"),
        "nettoyage": ("nettoyage", "entretien", "proprete", "menage"),
        "rh": ("recrutement", "emploi", "cv", "candidat", "recruteur"),
    }
    for secteur, kws in secteur_keywords.items():
        if any(kw in visible_text.lower() for kw in kws):
            result["secteur_detecte"] = secteur
            break

    # Detection du ton
    if "vous" in visible_text.lower() and "merci" in visible_text.lower():
        result["ton_detecte"] = "professionnel"
    if "tu " in visible_text.lower() or any(e in visible_text for e in ("😊", "👋", "🎉")):
        result["ton_detecte"] = "decontracte"
    if any(w in visible_text.lower() for w in ("excellence", "sur-mesure", "premium", "luxe")):
        result["ton_detecte"] = "premium"

    return result
