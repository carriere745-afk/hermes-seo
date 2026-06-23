"""T22 — AEO/GEO Technical Readiness.

Evalue la preparation technique du site pour les moteurs de reponse IA :
- llms.txt (standard emergent — equivalent IA de robots.txt)
- Directives AI dans robots.txt (GPTBot, CCBot, Claude-Web, Google-Extended,
  PerplexityBot, anthropic-ai, cohere-ai, AppleBot-Extended)
- Rich snippets eligibility (Reviews, FAQ, HowTo, Product) via balisage
- Citabilite du contenu : definitions, statistiques, citations
- Content freshness signals (datePublished, dateModified, schema)
- AI crawler blocking impact (si le site bloque les IA, il est invisible dans ChatGPT/Perplexity)

Sources :
- llms.txt spec : https://llmstxt.org/ (standard emergent 2025-2026)
- Google-Extended : https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers
- GPTBot : https://platform.openai.com/docs/gptbot
- CCBot / Claude-Web / anthropic-ai : documentation Anthropic

$0 — deterministe, httpx + BeautifulSoup + regex.
"""

import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt22")

UA = "HermesAudit/1.0"

# AI crawlers a verifier dans robots.txt
AI_CRAWLERS = {
    "GPTBot": {"label": "OpenAI / ChatGPT", "importance": "critical"},
    "CCBot": {"label": "Common Crawl (entrainement IA)", "importance": "high"},
    "Google-Extended": {"label": "Google Bard / Gemini / AI Overviews", "importance": "critical"},
    "Claude-Web": {"label": "Claude / Anthropic (recherche web)", "importance": "critical"},
    "anthropic-ai": {"label": "Anthropic AI (entrainement)", "importance": "high"},
    "PerplexityBot": {"label": "Perplexity AI", "importance": "critical"},
    "cohere-ai": {"label": "Cohere AI", "importance": "medium"},
    "AppleBot-Extended": {"label": "Apple Intelligence", "importance": "medium"},
    "Bytespider": {"label": "ByteDance / TikTok AI", "importance": "medium"},
    "Omgilibot": {"label": "Facebook / Meta AI", "importance": "medium"},
    "Amazonbot": {"label": "Amazon Alexa AI", "importance": "low"},
}

# Patterns de contenu citable par les IA
CITABILITY_PATTERNS = [
    (r"\b(?:definition|définition|qu'est-ce qu|c'est quoi)\b", "definition", 10),
    (r"\b\d{1,3}[.,]\d?\d?\s?%\b", "statistique/chiffre", 8),
    (r"\b\d{4}-\d{2}-\d{2}\b", "date precise", 5),
    (r"\b(?:selon|d'après|source|étude|rapport)\b", "citation/source", 8),
    (r"<blockquote|<q\b|<cite>", "balise citation HTML", 15),
    (r"<dfn\b|<abbr\b", "balise definition HTML", 10),
]


async def _fetch_path(base_url: str, path: str) -> tuple[int, str]:
    """Fetch un chemin relatif et retourne (status_code, content)."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            url = urljoin(base_url, path)
            resp = await client.get(url, headers={"User-Agent": UA})
            return resp.status_code, resp.text
    except Exception:
        return 0, ""


def _check_llms_txt(base_url: str, html: str) -> dict:
    """Verifie la presence et le contenu de llms.txt."""
    result = {
        "found": False,
        "status_code": 0,
        "sections": [],
        "issues": [],
    }

    # 1. Verifier le fichier /llms.txt
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            status, content = asyncio.ensure_future(_fetch_path(base_url, "/llms.txt")).result()
        else:
            status, content = asyncio.run(_fetch_path(base_url, "/llms.txt"))
    except Exception:
        status, content = 0, ""

    if status == 200 and content:
        result["found"] = True
        result["status_code"] = 200
        # Sections llms.txt (format markdown avec #)
        sections = re.findall(r"^##?\s+(.+)$", content, re.MULTILINE)
        result["sections"] = sections[:10]
    else:
        result["issues"].append({
            "severity": "medium",
            "description": "llms.txt absent — les IA n'ont pas d'index structure du site. Creez un fichier /llms.txt (https://llmstxt.org/)",
            "recommendation": "Creer un fichier /llms.txt listant les pages cles et leur description pour les IA"
        })

    # 2. Verifier le lien dans le HTML (<link rel="llms.txt">)
    soup = BeautifulSoup(html, "html.parser") if html else None
    if soup:
        link = soup.find("link", rel="llms.txt")
        if not link:
            result["issues"].append({
                "severity": "low",
                "description": "Pas de <link rel=\"llms.txt\"> dans le head — les IA ne peuvent pas le decouvrir automatiquement",
                "recommendation": "Ajouter <link rel=\"llms.txt\" href=\"/llms.txt\"> dans le <head>"
            })

    return result


def _check_ai_robots(robots_txt: str) -> dict:
    """Analyse les directives AI dans robots.txt."""
    result = {
        "crawlers_found": [],
        "crawlers_blocked": [],
        "crawlers_allowed": [],
        "ai_blocking_impact": "none",
        "issues": [],
    }

    if not robots_txt.strip():
        result["issues"].append({
            "severity": "low",
            "description": "robots.txt absent — impossible de controler les crawlers IA",
            "recommendation": "Creer un robots.txt avec des directives explicites pour les crawlers IA"
        })
        return result

    robots_lower = robots_txt.lower()

    for crawler_id, info in AI_CRAWLERS.items():
        pattern = rf"(?i)user-agent:\s*{re.escape(crawler_id)}"
        if re.search(pattern, robots_txt):
            result["crawlers_found"].append(crawler_id)
            # Verifier si bloque
            block_pattern = rf"(?i)user-agent:\s*{re.escape(crawler_id)}.*?disallow:\s*/(?:\s|$)"
            if re.search(block_pattern, robots_txt, re.DOTALL):
                result["crawlers_blocked"].append(crawler_id)
            else:
                result["crawlers_allowed"].append(crawler_id)

    # Impact blocking
    critical_blocked = [c for c in result["crawlers_blocked"] if AI_CRAWLERS[c]["importance"] == "critical"]
    if critical_blocked:
        result["ai_blocking_impact"] = "critical"
        names = [AI_CRAWLERS[c]["label"] for c in critical_blocked]
        result["issues"].append({
            "severity": "critical",
            "description": f"Site invisible pour les IA majeures : {', '.join(names)}. Les crawlers sont bloques dans robots.txt.",
            "recommendation": f"Autoriser {', '.join(critical_blocked)} si vous voulez apparaitre dans ChatGPT, Google AI Overviews, Perplexity"
        })
    elif result["crawlers_blocked"]:
        result["ai_blocking_impact"] = "partial"
        names = [AI_CRAWLERS[c]["label"] for c in result["crawlers_blocked"]]
        result["issues"].append({
            "severity": "medium",
            "description": f"Certains crawlers IA bloques : {', '.join(names)}",
            "recommendation": "Verifier si le blocage est intentionnel"
        })

    # Aucune directive = tous les AI crawlers sont autorises par defaut
    if not result["crawlers_found"]:
        result["issues"].append({
            "severity": "low",
            "description": "Aucune directive specifique pour les crawlers IA dans robots.txt — ils sont autorises par defaut, mais aucune strategie visible",
            "recommendation": "Ajouter des directives explicites pour GPTBot, Google-Extended, Claude-Web, PerplexityBot"
        })

    return result


def _check_citability(html: str) -> dict:
    """Evalue la citabilite du contenu par les IA."""
    result = {
        "score": 0,
        "max_score": 50,
        "signals_found": [],
        "signals_missing": [],
    }

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text() if soup else html

    total_weight = 0
    for pattern, signal_name, weight in CITABILITY_PATTERNS:
        matches = re.findall(pattern, text[:10000], re.IGNORECASE)
        if matches:
            result["score"] += weight
            result["signals_found"].append(signal_name)
        else:
            result["signals_missing"].append(signal_name)
        total_weight += weight

    result["max_score"] = total_weight
    return result


def _check_freshness_signals(html: str, json_ld_types: list[str]) -> dict:
    """Verifie les signaux de fraicheur du contenu."""
    result = {
        "has_date_published": False,
        "has_date_modified": False,
        "has_schema_date": False,
        "score": 0,
        "issues": [],
    }

    soup = BeautifulSoup(html, "html.parser")

    # Meta date
    for meta in soup.find_all("meta"):
        if meta.get("name", "").lower() in ("date", "pubdate", "publish_date"):
            result["has_date_published"] = True
        if meta.get("property", "").lower() in ("article:published_time", "article:modified_time"):
            result["has_date_published"] = True

    # HTML5 time element
    if soup.find("time", attrs={"datetime": True}):
        result["has_date_published"] = True
        result["has_date_modified"] = True

    # Schema date
    if any(t in json_ld_types for t in ("Article", "NewsArticle", "BlogPosting", "WebPage")):
        result["has_schema_date"] = True

    # Scoring
    if result["has_date_published"]:
        result["score"] += 35
    if result["has_date_modified"]:
        result["score"] += 35
    if result["has_schema_date"]:
        result["score"] += 30

    if result["score"] < 50:
        result["issues"].append({
            "severity": "high",
            "description": "Signaux de fraicheur faibles — les IA et Google valorisent les contenus avec date de publication visible et schema dateModified",
            "recommendation": "Ajouter datePublished/dateModified en schema JSON-LD + afficher la date sur la page"
        })

    return result


async def run(state: TechAuditState) -> TechAuditState:
    """Evalue la preparation technique AEO/GEO du site."""
    state.current_agent = "tt22"

    if not state.crawled_pages:
        return state

    pages_ok = [p for p in state.crawled_pages if p.status_code == 200 and not p.fetch_error]
    if not pages_ok:
        return state

    logger.info(f"T22: AEO/GEO technical readiness for {len(pages_ok)} pages")

    issue_counter = len(state.issues)
    homepage = pages_ok[0]
    homepage_html = ""

    # Fetch homepage HTML (not stored in crawled_pages at this level)
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(homepage.url, headers={"User-Agent": UA, "Accept": "text/html"})
            if resp.status_code == 200:
                homepage_html = resp.text
    except Exception:
        pass

    # 1. llms.txt
    llms = _check_llms_txt(state.site_url, homepage_html)
    for iss in llms.get("issues", []):
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}", category="aeo_geo",
            description=f"llms.txt: {iss['description']}",
            url=f"{state.site_url}/llms.txt", observed=iss["description"],
            rule="llms.txt present et decouvert", confidence="high",
            source_agent="T22", severity=iss["severity"],
            impact_business="High" if iss["severity"] == "critical" else "Medium",
            gain_potentiel="High",
            effort="30 min — Creer le fichier selon https://llmstxt.org/",
            priority="P1" if iss["severity"] in ("critical", "high") else "P2",
        ))

    # 2. AI directives robots.txt
    ai_robots = _check_ai_robots(state.robots_txt)
    for iss in ai_robots.get("issues", []):
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}", category="aeo_geo",
            description=iss["description"],
            url=state.site_url, observed=iss["description"],
            rule="robots.txt avec directives AI", confidence="high",
            source_agent="T22", severity=iss["severity"],
            impact_business="High" if iss["severity"] == "critical" else "Medium",
            gain_potentiel="High",
            effort="15 min — Ajouter les directives dans robots.txt",
            priority="P0" if iss["severity"] == "critical" else "P2",
        ))

    # Info AI (stockee dans l'URL pour le rapport, pas dans le modele)
    ai_summary = {
        "found": ai_robots["crawlers_found"],
        "blocked": ai_robots["crawlers_blocked"],
        "allowed": ai_robots["crawlers_allowed"],
        "impact": ai_robots["ai_blocking_impact"],
    }
    logger.info(f"T22: AI crawlers - found={len(ai_summary['found'])}, blocked={len(ai_summary['blocked'])}, impact={ai_summary['impact']}")
    _ = ai_summary  # Consomme (utilise dans le rapport via les issues generees)

    # 3. Rich snippets eligibility (via T09 data)
    has_product_schema = any("Product" in p.json_ld_types for p in pages_ok)
    has_faq_schema = any("FAQPage" in p.json_ld_types for p in pages_ok)
    has_article_schema = any("Article" in p.json_ld_types for p in pages_ok)

    product_pages = sum(1 for p in pages_ok if "Product" not in p.json_ld_types)
    if product_pages > len(pages_ok) * 0.5:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}", category="aeo_geo",
            description=f"Schema Product manquant sur {product_pages} fiches — eligible rich snippets Google Shopping",
            url=state.site_url, observed=f"pages_without_Product_schema: {product_pages}/{len(pages_ok)}",
            rule="Product schema sur pages produit", confidence="high",
            source_agent="T22", severity="high",
            impact_business="High", gain_potentiel="High",
            effort="Ajouter Product JSON-LD — PrestaShop: Module SEO > Schema",
            priority="P1",
        ))

    # 4. Citabilite (analyser homepage + 2 pages)
    for page in pages_ok[:3]:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(page.url, headers={"User-Agent": UA, "Accept": "text/html"})
                if resp.status_code == 200:
                    cit = _check_citability(resp.text)
                    if cit["score"] < 20:
                        issue_counter += 1
                        state.issues.append(TechIssue(
                            id=f"P-{issue_counter:03d}", category="aeo_geo",
                            description=f"Citabilite faible ({cit['score']}/{cit['max_score']}) — le contenu n'est pas structure pour etre cite par les IA",
                            url=page.url,
                            observed=f"citability_score: {cit['score']}/{cit['max_score']}, missing: {', '.join(cit['signals_missing'][:3])}",
                            rule="contenu citable (definitions, stats, citations)",
                            confidence="medium", source_agent="T22",
                            severity="medium", impact_business="Medium",
                            gain_potentiel="High",
                            effort="Ajouter definitions, statistiques, sources citables",
                            priority="P2",
                        ))
                        break  # Une seule issue de citabilité globale
        except Exception:
            pass

    # 5. Freshness signals
    for page in pages_ok[:3]:
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(page.url, headers={"User-Agent": UA, "Accept": "text/html"})
                if resp.status_code == 200:
                    fresh = _check_freshness_signals(resp.text, page.json_ld_types)
                    if fresh["score"] < 50:
                        issue_counter += 1
                        state.issues.append(TechIssue(
                            id=f"P-{issue_counter:03d}", category="aeo_geo",
                            description=f"Signaux de fraicheur faibles ({fresh['score']}/100) — pas de date de publication visible",
                            url=page.url,
                            observed=f"freshness_score: {fresh['score']}/100",
                            rule="dates de publication et schema dateModified presents",
                            confidence="high", source_agent="T22",
                            severity="high" if fresh["score"] < 30 else "medium",
                            impact_business="Medium", gain_potentiel="High",
                            effort="Ajouter datePublished dans le schema JSON-LD + date visible",
                            priority="P2",
                        ))
                        break
        except Exception:
            pass

    logger.info(f"T22: llms.txt={'found' if llms['found'] else 'missing'}, AI crawlers found={len(ai_robots['crawlers_found'])}, blocked={len(ai_robots['crawlers_blocked'])}")

    # 6. GEO Optimizer (external OSS audit, optional)
    try:
        from hermes.connectors.geo_optimizer_connector import audit_aeo_geo
        geo_result = await audit_aeo_geo(state.site_url)
        if not geo_result.get("error") and geo_result["score"] > 0:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}", category="aeo_geo",
                description=f"AEO/GEO Score (geo-optimizer): {geo_result['score']}/100 (band {geo_result['band']})",
                url=state.site_url,
                observed=f"geo_optimizer_score: {geo_result['score']}, robots={geo_result['robots_score']}, llms={geo_result['llms_txt_score']}, schema={geo_result['schema_score']}",
                rule="score AEO/GEO > 70", confidence="high",
                source_agent="T22", severity="medium" if geo_result["score"] < 50 else "low",
                impact_business="High", gain_potentiel="High",
                effort="Suivre les recommandations du rapport geo-optimizer",
                priority="P2" if geo_result["score"] < 50 else "P3",
            ))
            for reco in geo_result.get("recommendations", [])[:3]:
                issue_counter += 1
                state.issues.append(TechIssue(
                    id=f"P-{issue_counter:03d}", category="aeo_geo",
                    description=f"GEO Reco: {reco[:130]}",
                    url=state.site_url, observed=reco[:100],
                    rule="geo-optimizer recommendation", confidence="medium",
                    source_agent="T22", severity="low",
                    impact_business="Medium", gain_potentiel="Medium",
                    effort="Appliquer la recommandation", priority="P3",
                ))
    except Exception as e:
        logger.debug(f"T22: geo-optimizer skipped ({e})")

    state.updated_at = datetime.now()
    return state
