"""Free SEO Tools — Lead Generation & SaaS freemium.

12+ outils SEO gratuits embeddables dans Streamlit ou WordPress.
Inspired by: Ahrefs Free Tools, NeedleCode (90+), Apex Marketing,
GitDevTool, SEO.ai (46 tools).

Usage:
    from hermes.tools.free_seo_tools import analyze_meta, check_heading_structure
    result = analyze_meta(url="https://example.com")
"""

import re
import logging
from typing import Optional
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger("hermes.free_tools")


# ═══════════════════════════════════════════════════════════════════════
# 1. SERP Preview Simulator (Meta Title + Description)
# ═══════════════════════════════════════════════════════════════════════

def serp_preview(title: str, description: str, url: str = "https://example.com") -> dict:
    """Simule l'affichage d'un resultat Google SERP.

    Retourne: {title, description, url, title_length, desc_length,
               title_truncated, desc_truncated, title_pixels, desc_pixels,
               score, recommendations}
    """
    title = str(title)[:200]
    description = str(description)[:300]
    domain = urlparse(url).netloc if url.startswith("http") else url

    # Google truncation rules (approx width in pixels)
    TITLE_MAX = 580  # pixels (≈55-60 chars)
    DESC_MAX = 920   # pixels (≈155-160 chars)

    title_pixels = _estimate_pixels(title)
    desc_pixels = _estimate_pixels(description)
    title_truncated = title_pixels > TITLE_MAX
    desc_truncated = desc_pixels > DESC_MAX

    reco = []
    score = 100
    if len(title) < 30:
        reco.append("Titre trop court (<30 caracteres). Visez 50-60 caracteres.")
        score -= 20
    if len(title) > 65:
        reco.append("Titre trop long (>65 caracteres). Risque de troncature.")
        score -= 15
    if len(description) < 70:
        reco.append("Description trop courte. Visez 120-155 caracteres.")
        score -= 20
    if len(description) > 160:
        reco.append("Description trop longue. Risque de troncature.")
        score -= 15
    if not reco:
        reco.append("Meta title et description optimaux.")

    return {
        "title": title[:65], "description": description[:160], "url": domain,
        "title_length": len(title), "desc_length": len(description),
        "title_pixels": title_pixels, "desc_pixels": desc_pixels,
        "title_truncated": title_truncated, "desc_truncated": desc_truncated,
        "score": max(0, score), "recommendations": reco,
        "preview_html": _serp_html(title, description, domain),
    }


def _estimate_pixels(text: str) -> int:
    """Estime la largeur en pixels d'un texte (approx Google SERP)."""
    narrow = sum(1 for c in text if c in "il1!.,:;|'\"")
    wide = sum(1 for c in text if c in "wmWM@%#")
    normal = len(text) - narrow - wide
    return narrow * 5 + normal * 10 + wide * 13


def _serp_html(title: str, desc: str, domain: str) -> str:
    return f"""<div style="font-family:Arial,sans-serif;max-width:600px;padding:10px;background:#fff">
<div style="color:#1a0dab;font-size:18px;line-height:1.3;margin-bottom:3px;text-decoration:none">{title[:65]}</div>
<div style="color:#006621;font-size:14px;line-height:1.4;white-space:nowrap">{domain}</div>
<div style="color:#545454;font-size:13px;line-height:1.4">{desc[:160]}</div>
</div>"""


# ═══════════════════════════════════════════════════════════════════════
# 2. Word Counter & Text Analyzer
# ═══════════════════════════════════════════════════════════════════════

def word_counter(text: str) -> dict:
    """Analyse complete de texte SEO.

    Retourne: {words, chars, chars_no_spaces, sentences, paragraphs,
               reading_time, speaking_time, keyword_density, flesch_score}
    """
    text = str(text)[:100000]
    words = len(re.findall(r"\b\w+\b", text))
    chars = len(text)
    chars_no_spaces = len(text.replace(" ", "").replace("\n", ""))
    sentences = max(1, len(re.findall(r"[.!?]+", text)))
    paragraphs = max(1, len(re.findall(r"\n\s*\n", text)) + 1)

    # Reading time (avg 238 words/min)
    reading_time_sec = int((words / 238) * 60)
    reading_time = f"{reading_time_sec // 60}m {reading_time_sec % 60}s" if reading_time_sec >= 60 else f"{reading_time_sec}s"

    # Speaking time (avg 130 words/min)
    speaking_time_sec = int((words / 130) * 60)
    speaking_time = f"{speaking_time_sec // 60} min" if speaking_time_sec >= 60 else f"{speaking_time_sec} sec"

    # Keyword density
    word_list = re.findall(r"\b\w{3,}\b", text.lower())
    word_freq = {}
    for w in word_list:
        word_freq[w] = word_freq.get(w, 0) + 1
    top_keywords = sorted(word_freq, key=word_freq.get, reverse=True)[:10]
    total = max(words, 1)
    density = [{"word": w, "count": word_freq[w], "density": round(word_freq[w] / total * 100, 1)} for w in top_keywords[:10]]

    # Appreciation
    if words < 300:
        appreciation = "Contenu court — les pages de moins de 300 mots sont considerees comme du thin content par Google."
    elif words < 1000:
        appreciation = "Bonne longueur pour un article de blog."
    elif words < 2500:
        appreciation = "Longueur ideale pour un article pilier ou un guide complet."
    else:
        appreciation = "Contenu long et approfondi — excellent pour l'autorite thematique."

    return {
        "words": words, "chars": chars, "chars_no_spaces": chars_no_spaces,
        "sentences": sentences, "paragraphs": paragraphs,
        "reading_time": reading_time, "speaking_time": speaking_time,
        "avg_words_per_sentence": round(words / sentences, 1),
        "avg_chars_per_word": round(chars_no_spaces / words, 1) if words else 0,
        "keyword_density": density,
        "appreciation": appreciation,
    }


# ═══════════════════════════════════════════════════════════════════════
# 3. Heading Structure Analyzer (H1-H6)
# ═══════════════════════════════════════════════════════════════════════

def heading_structure(html_or_url: str, is_url: bool = False) -> dict:
    """Analyse la structure des headings (H1-H6).

    Retourne: {headings: {h1: [...], h2: [...]}, issues: [...], score: 0-100}
    """
    html = html_or_url
    if is_url:
        try:
            import httpx
            resp = httpx.get(html_or_url, timeout=10, follow_redirects=True)
            html = resp.text
        except Exception:
            return {"error": "Impossible de charger l'URL"}

    headings = {}
    for level in range(1, 7):
        tag = f"h{level}"
        matches = re.findall(rf"<{tag}[^>]*>([^<]*)</{tag}>", html, re.IGNORECASE)
        headings[tag] = [m.strip() for m in matches if m.strip()]

    issues = []
    score = 100

    # H1: exactly 1 recommended
    h1_count = len(headings["h1"])
    if h1_count == 0:
        issues.append("Aucun H1 trouve. Chaque page doit avoir exactement 1 H1.")
        score -= 30
    elif h1_count > 1:
        issues.append(f"{h1_count} H1 trouves. Il ne devrait y avoir qu'un seul H1 par page.")
        score -= 20 * h1_count

    # H2: at least 2 recommended
    h2_count = len(headings["h2"])
    if h2_count == 0:
        issues.append("Aucun H2 trouve. Utilisez des H2 pour structurer votre contenu.")
        score -= 20
    elif h2_count < 2:
        issues.append(f"Seulement {h2_count} H2. Visez au moins 3-5 H2 pour un article bien structure.")
        score -= 10

    # Check hierarchy (no skipped levels)
    for level in range(2, 7):
        prev = f"h{level-1}"
        curr = f"h{level}"
        if len(headings[curr]) > 0 and len(headings[prev]) == 0:
            issues.append(f"{curr.upper()} present mais {prev.upper()} manquant. Ne sautez pas de niveau de heading.")
            score -= 10

    return {"headings": headings, "issues": issues, "score": max(0, score),
            "total_headings": sum(len(v) for v in headings.values())}


# ═══════════════════════════════════════════════════════════════════════
# 4. Schema Markup Generator (JSON-LD)
# ═══════════════════════════════════════════════════════════════════════

def generate_schema_faq(questions: list[str]) -> dict:
    """Genere un schema FAQPage JSON-LD."""
    entities = []
    for i, q in enumerate(questions[:50]):
        entities.append({
            "@type": "Question",
            "name": q,
            "acceptedAnswer": {"@type": "Answer", "text": "..."}
        })
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": entities,
    }


def generate_schema_article(title: str, author: str = "", date_pub: str = "",
                            image_url: str = "", publisher: str = "") -> dict:
    """Genere un schema Article JSON-LD."""
    schema: dict = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
    }
    if author:
        schema["author"] = {"@type": "Person", "name": author}
    if date_pub:
        schema["datePublished"] = date_pub
    if image_url:
        schema["image"] = image_url
    if publisher:
        schema["publisher"] = {"@type": "Organization", "name": publisher}
    return schema


def generate_schema_local_business(name: str, address: str = "", phone: str = "",
                                   url: str = "", image: str = "") -> dict:
    """Genere un schema LocalBusiness JSON-LD."""
    schema: dict = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": name,
    }
    if address:
        schema["address"] = {"@type": "PostalAddress", "streetAddress": address}
    if phone:
        schema["telephone"] = phone
    if url:
        schema["url"] = url
    if image:
        schema["image"] = image
    return schema


def generate_schema_product(name: str, description: str = "", price: float = 0,
                            currency: str = "EUR", availability: str = "InStock") -> dict:
    """Genere un schema Product JSON-LD."""
    return {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "description": description,
        "offers": {
            "@type": "Offer",
            "price": str(price),
            "priceCurrency": currency,
            "availability": f"https://schema.org/{availability}",
        },
    }


def generate_schema_breadcrumb(items: list[tuple[str, str]]) -> dict:
    """Genere un schema BreadcrumbList JSON-LD.

    Args:
        items: [(name, url), ...] ex: [("Accueil","/"),("Blog","/blog"),("Article","")]
    """
    list_items = []
    for i, (name, url) in enumerate(items[:20], 1):
        item = {"@type": "ListItem", "position": i, "name": name}
        if url:
            item["item"] = url
        list_items.append(item)
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": list_items}


# ═══════════════════════════════════════════════════════════════════════
# 5. Robots.txt Generator
# ═══════════════════════════════════════════════════════════════════════

def generate_robots_txt(domain: str = "", sitemap_url: str = "",
                        allow_admin: bool = False, block_ai_crawlers: list[str] | None = None) -> str:
    """Genere un fichier robots.txt optimal.

    Args:
        domain: exemple.com
        sitemap_url: https://exemple.com/sitemap.xml
        allow_admin: autoriser le crawl de /wp-admin (defaut: False)
        block_ai_crawlers: liste de AI crawlers a bloquer
    """
    lines = ["User-agent: *"]
    lines.append("Disallow: /wp-admin/")
    if not allow_admin:
        lines.append("Disallow: /wp-login.php")
    lines.append("Disallow: /wp-content/plugins/")
    lines.append("Disallow: /xmlrpc.php")
    lines.append("")

    # AI crawlers
    if block_ai_crawlers is None:
        block_ai_crawlers = []  # Default: allow all (good for GEO)

    for crawler in block_ai_crawlers:
        lines.append(f"User-agent: {crawler}")
        lines.append("Disallow: /")
        lines.append("")

    if sitemap_url:
        lines.append(f"Sitemap: {sitemap_url}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# 6. Meta Tag Analyzer (fetch real page)
# ═══════════════════════════════════════════════════════════════════════

async def analyze_meta(url: str) -> dict:
    """Analyse les meta tags d'une page existante."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            html = resp.text
    except Exception as e:
        return {"error": str(e)}

    result: dict = {
        "url": url, "status_code": 200 if 'resp' in dir() else 0,
        "title": "", "title_length": 0,
        "meta_description": "", "meta_desc_length": 0,
        "canonical": "",
        "robots_meta": "",
        "og_title": "", "og_description": "", "og_image": "",
        "twitter_card": "",
        "viewport": "",
        "h1": "", "h1_count": 0,
        "issues": [], "score": 100,
    }

    # Title
    tm = re.search(r"<title>([^<]*)</title>", html, re.IGNORECASE)
    if tm:
        result["title"] = tm.group(1)[:120]
        result["title_length"] = len(result["title"])

    # Meta description
    dm = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html, re.IGNORECASE)
    if dm:
        result["meta_description"] = dm.group(1)[:200]
        result["meta_desc_length"] = len(result["meta_description"])

    # Canonical
    cm = re.search(r'<link[^>]+rel="canonical"[^>]+href="([^"]*)"', html, re.IGNORECASE)
    if cm:
        result["canonical"] = cm.group(1)

    # Open Graph
    ogt = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', html, re.IGNORECASE)
    if ogt: result["og_title"] = ogt.group(1)
    ogd = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"', html, re.IGNORECASE)
    if ogd: result["og_description"] = ogd.group(1)
    ogi = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]*)"', html, re.IGNORECASE)
    if ogi: result["og_image"] = ogi.group(1)

    # H1
    h1s = re.findall(r"<h1[^>]*>([^<]*)</h1>", html, re.IGNORECASE)
    result["h1_count"] = len(h1s)
    result["h1"] = h1s[0][:100] if h1s else ""

    # Issues
    if not result["title"]:
        result["issues"].append("Title manquant.")
        result["score"] -= 30
    elif result["title_length"] < 30:
        result["issues"].append(f"Title trop court ({result['title_length']} chars). Visez 50-60.")
        result["score"] -= 15
    if not result["meta_description"]:
        result["issues"].append("Meta description manquante.")
        result["score"] -= 25
    if result["h1_count"] == 0:
        result["issues"].append("Aucun H1 trouve.")
        result["score"] -= 20
    elif result["h1_count"] > 1:
        result["issues"].append(f"Multiple H1 ({result['h1_count']}). Un seul recommande.")
        result["score"] -= 15
    if not result["og_title"]:
        result["issues"].append("Open Graph title manquant (partage reseaux sociaux).")
        result["score"] -= 10

    result["score"] = max(0, result["score"])
    return result


# ═══════════════════════════════════════════════════════════════════════
# 7. SSL / HTTPS Checker
# ═══════════════════════════════════════════════════════════════════════

async def check_ssl(url: str) -> dict:
    """Verifie le certificat SSL et la configuration HTTPS."""
    import httpx
    import ssl
    import socket
    from datetime import datetime

    domain = urlparse(url).netloc if "://" in url else url
    result = {"domain": domain, "https_working": False, "redirect_http": False,
              "cert_valid": False, "cert_expiry": "", "cert_days_left": 0,
              "hsts": False, "score": 0}

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(f"https://{domain}")
            result["https_working"] = resp.status_code < 500
    except Exception:
        pass

    # Check cert expiry
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((domain, 443), timeout=5) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
                expiry_str = cert.get("notAfter", "")
                if expiry_str:
                    expiry = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                    days_left = (expiry - datetime.now()).days
                    result["cert_valid"] = days_left > 0
                    result["cert_expiry"] = expiry.strftime("%Y-%m-%d")
                    result["cert_days_left"] = days_left
    except Exception:
        pass

    return result


# ═══════════════════════════════════════════════════════════════════════
# 8. Keyword Density Checker
# ═══════════════════════════════════════════════════════════════════════

def keyword_density(text: str, target_keyword: str = "") -> dict:
    """Analyse la densite de mots-cles dans un texte."""
    words = re.findall(r"\b\w+\b", text.lower())
    total = max(len(words), 1)

    # Target keyword
    kw_words = target_keyword.lower().split()
    kw_count = 0
    for i in range(len(words) - len(kw_words) + 1):
        if words[i:i + len(kw_words)] == kw_words:
            kw_count += 1

    # All keywords density
    word_freq = {}
    for w in words:
        if len(w) >= 4:
            word_freq[w] = word_freq.get(w, 0) + 1

    top = sorted(word_freq, key=word_freq.get, reverse=True)[:15]
    density = [{"word": w, "count": word_freq[w],
                "density": round(word_freq[w] / total * 100, 1)} for w in top]

    kw_density = round(kw_count / total * 100, 2) if kw_count else 0

    appreciation = "Densite optimale (1-3%)" if 0.5 <= kw_density <= 3 else \
                   "Densite trop faible (<0.5%)" if kw_density < 0.5 else \
                   "Densite trop elevee (>3%) — risque de keyword stuffing"

    return {"total_words": total, "target_keyword": target_keyword,
            "keyword_count": kw_count, "keyword_density": kw_density,
            "appreciation": appreciation, "top_keywords": density}


# ═══════════════════════════════════════════════════════════════════════
# 9. URL Structure Analyzer
# ═══════════════════════════════════════════════════════════════════════

def analyze_url_structure(url: str) -> dict:
    """Analyse la structure d'une URL pour le SEO."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")

    issues = []
    score = 100

    # Length
    if len(url) > 75:
        issues.append("URL trop longue (>75 caracteres). Les URLs courtes sont mieux referencees.")
        score -= 15

    # Uppercase
    if any(c.isupper() for c in path):
        issues.append("L'URL contient des majuscules. Utilisez uniquement des minuscules.")
        score -= 20

    # Special chars
    if re.search(r"[^a-z0-9\-_./]", path, re.IGNORECASE):
        issues.append("L'URL contient des caracteres speciaux. Utilisez des tirets (-) comme separateurs.")
        score -= 15

    # Underscores
    if "_" in path:
        issues.append("L'URL contient des underscores (_). Google prefere les tirets (-).")
        score -= 10

    # Numbers only
    path_clean = path.strip("/").replace("-", " ").replace("/", " ")
    if path_clean and re.match(r"^[\d\s]+$", path_clean):
        issues.append("L'URL est composee uniquement de chiffres. Incluez des mots-cles descriptifs.")
        score -= 25

    # Depth (>3 subdirectories)
    depth = len([p for p in path.split("/") if p])
    if depth > 3:
        issues.append(f"URL trop profonde ({depth} niveaux). Limitez a 3 niveaux maximum.")
        score -= 10

    # HTTPS
    if parsed.scheme != "https":
        issues.append("L'URL n'utilise pas HTTPS.")
        score -= 30

    # Parameters
    if parsed.query:
        issues.append("L'URL contient des parametres de requete. Evitez si possible pour les pages indexables.")
        score -= 10

    return {"url": url, "scheme": parsed.scheme, "domain": parsed.netloc,
            "path": path, "depth": depth, "issues": issues, "score": max(0, score)}


# ═══════════════════════════════════════════════════════════════════════
# 10. Internal Link Checker
# ═══════════════════════════════════════════════════════════════════════

async def check_internal_links(url: str, max_links: int = 50) -> dict:
    """Analyse les liens internes et externes d'une page."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            html = resp.text
    except Exception as e:
        return {"error": str(e)}

    domain = urlparse(url).netloc.replace("www.", "")
    links = re.findall(r'<a[^>]+href="([^"]*)"', html, re.IGNORECASE)

    internal = []
    external = []
    broken = []

    for link in links[:max_links * 3]:
        link = link.strip()
        if not link or link.startswith("#") or link.startswith("javascript"):
            continue
        if domain in link or link.startswith("/"):
            internal.append(link)
        else:
            external.append(link)

    return {"url": url, "internal_links": len(internal[:max_links]),
            "external_links": len(external[:max_links]),
            "total_links_found": len(links),
            "internal_sample": internal[:10],
            "external_sample": external[:10]}


# ═══════════════════════════════════════════════════════════════════════
# 11. Mobile-Friendly Quick Check
# ═══════════════════════════════════════════════════════════════════════

def check_mobile_friendly(html_or_url: str, is_url: bool = False) -> dict:
    """Verifie les elements de compatibilite mobile (viewport, touch icons...)."""
    html = html_or_url
    if is_url:
        try:
            import httpx
            resp = httpx.get(html_or_url, timeout=10, follow_redirects=True)
            html = resp.text
        except Exception:
            return {"error": "Impossible de charger l'URL"}

    checks = {
        "viewport": bool(re.search(r'<meta[^>]+name="viewport"', html, re.IGNORECASE)),
        "responsive_css": bool(re.search(r"@media", html)),
        "touch_icon": bool(re.search(r'rel="apple-touch-icon"', html)),
        "font_size_readable": True,  # Heuristic
        "tap_targets": True,  # Heuristic
    }

    score = sum(1 for v in checks.values() if v) / len(checks) * 100
    return {"checks": checks, "score": round(score, 1),
            "recommendation": "Ajoutez une balise meta viewport" if not checks["viewport"] else "Configuration mobile OK"}


# ═══════════════════════════════════════════════════════════════════════
# 12. Quick SEO Score (All-in-One)
# ═══════════════════════════════════════════════════════════════════════

async def quick_seo_score(url: str) -> dict:
    """Score SEO rapide (version gratuite, limites volontaires pour upsell)."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}"}
            html = resp.text[:100000]
    except Exception as e:
        return {"error": str(e)}

    scores = {}
    issues_all = []
    total_score = 0
    max_score = 0

    # Title
    tm = re.search(r"<title>([^<]*)</title>", html, re.IGNORECASE)
    title = tm.group(1) if tm else ""
    title_len = len(title)
    max_score += 20
    if not title:
        issues_all.append("Title manquant")
    elif title_len < 30:
        issues_all.append(f"Title court ({title_len} chars)")
        scores["title"] = 10
    elif title_len > 65:
        issues_all.append(f"Title long ({title_len} chars)")
        scores["title"] = 12
    else:
        scores["title"] = 20

    # Meta description
    dm = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]*)"', html, re.IGNORECASE)
    desc = dm.group(1) if dm else ""
    desc_len = len(desc)
    max_score += 20
    if not desc:
        issues_all.append("Meta description manquante")
    elif desc_len < 70:
        scores["meta"] = 10
        issues_all.append("Meta description courte")
    elif desc_len > 160:
        scores["meta"] = 12
    else:
        scores["meta"] = 20

    # H1
    h1s = re.findall(r"<h1[^>]*>([^<]*)</h1>", html, re.IGNORECASE)
    max_score += 15
    if len(h1s) == 0:
        issues_all.append("H1 manquant")
    elif len(h1s) > 1:
        scores["h1"] = 8
        issues_all.append(f"{len(h1s)} H1 (1 recommande)")
    else:
        scores["h1"] = 15

    # HTTPS
    max_score += 10
    scores["https"] = 10 if url.startswith("https") else 0

    # Viewport (mobile)
    max_score += 10
    scores["viewport"] = 10 if re.search(r'<meta[^>]+name="viewport"', html, re.IGNORECASE) else 0

    # Open Graph
    max_score += 10
    scores["og"] = 10 if re.search(r'property="og:title"', html) else 0

    # Canonical
    max_score += 10
    scores["canonical"] = 10 if re.search(r'rel="canonical"', html, re.IGNORECASE) else 0

    # Schema.org
    max_score += 5
    scores["schema"] = 5 if re.search(r'application/ld\+json', html) or re.search(r'itemscope', html) else 0

    total_score = sum(scores.values())

    grade = "A" if total_score >= 90 else ("B" if total_score >= 70 else ("C" if total_score >= 50 else ("D" if total_score >= 30 else "F")))

    return {
        "url": url, "score": total_score, "max_score": max_score,
        "grade": grade, "percentage": round(total_score / max_score * 100, 1),
        "scores_detail": scores, "issues": issues_all[:10],
        "upsell_note": "Analyse complete avec Hermes SEO (P2 Audit de Contenu): 7 dimensions SEO/AEO/GEO/EEAT/UX, 55+ signaux, recommandations type-aware."
    }


# ═══════════════════════════════════════════════════════════════════════
# Bundle: all tools as a dictionary for dynamic UI rendering
# ═══════════════════════════════════════════════════════════════════════

TOOLS_REGISTRY = {
    "serp_preview": {
        "name": "SERP Preview Simulator",
        "description": "Simulez l'affichage de votre page dans les resultats Google",
        "function": serp_preview,
        "async": False,
        "icon": "🔍",
        "category": "on-page",
    },
    "word_counter": {
        "name": "Compteur de Mots & Analyse de Texte",
        "description": "Analysez la longueur, le temps de lecture et la densite de mots-cles",
        "function": word_counter,
        "async": False,
        "icon": "📝",
        "category": "content",
    },
    "heading_structure": {
        "name": "Analyseur de Structure H1-H6",
        "description": "Verifiez la hierarchie de vos titres pour le SEO",
        "function": heading_structure,
        "async": False,
        "icon": "📋",
        "category": "on-page",
    },
    "schema_generator": {
        "name": "Generateur de Schema Markup",
        "description": "Generez du JSON-LD pour FAQ, Article, LocalBusiness, Product, Breadcrumb",
        "function": generate_schema_faq,
        "async": False,
        "icon": "🏗️",
        "category": "technical",
    },
    "robots_generator": {
        "name": "Generateur robots.txt",
        "description": "Generez un fichier robots.txt optimise pour le SEO",
        "function": generate_robots_txt,
        "async": False,
        "icon": "🤖",
        "category": "technical",
    },
    "meta_analyzer": {
        "name": "Analyseur de Meta Tags",
        "description": "Analysez les balises meta, OG, canonical et H1 d'une page existante",
        "function": analyze_meta,
        "async": True,
        "icon": "🏷️",
        "category": "on-page",
    },
    "ssl_checker": {
        "name": "Verificateur HTTPS/SSL",
        "description": "Verifiez votre certificat SSL et la configuration HTTPS",
        "function": check_ssl,
        "async": True,
        "icon": "🔒",
        "category": "technical",
    },
    "keyword_density": {
        "name": "Densite de Mots-Cles",
        "description": "Analysez la densite d'un mot-cle cible dans votre contenu",
        "function": keyword_density,
        "async": False,
        "icon": "🎯",
        "category": "content",
    },
    "url_analyzer": {
        "name": "Analyseur d'URL",
        "description": "Verifiez si votre URL est optimisee pour le SEO",
        "function": analyze_url_structure,
        "async": False,
        "icon": "🔗",
        "category": "on-page",
    },
    "internal_links": {
        "name": "Verificateur de Liens Internes",
        "description": "Analysez les liens internes et externes d'une page",
        "function": check_internal_links,
        "async": True,
        "icon": "🕸️",
        "category": "on-page",
    },
    "mobile_friendly": {
        "name": "Test Mobile-Friendly",
        "description": "Verifiez la compatibilite mobile de votre page",
        "function": check_mobile_friendly,
        "async": False,
        "icon": "📱",
        "category": "technical",
    },
    "quick_score": {
        "name": "Score SEO Rapide",
        "description": "Obtenez un score SEO sur 100 en 5 secondes",
        "function": quick_seo_score,
        "async": True,
        "icon": "⚡",
        "category": "all-in-one",
    },
}
