"""T04 — Sitemap & Robots.txt.

Analyse les sitemaps et le fichier robots.txt :
- Detection et parsing des sitemaps (reutilise sitemap_parser.py)
- Validation robots.txt (via protego)
- Comparaison sitemap vs pages crawlees
- Detection des URLs dans le sitemap mais non crawlees
- Detection des URLs crawlees mais absentes du sitemap
- Verification des directives Disallow

$0 — pas de LLM. Reutilise sitemap_parser.py et protego.
"""

import logging
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx

from hermes.models.audit_tech import TechAuditState, TechIssue

logger = logging.getLogger("hermes.audit_tech.tt04")


async def _fetch_robots_txt(base_url: str) -> tuple[str, str]:
    """Recupere le contenu de robots.txt.

    Returns: (content, url) ou ("", base_url)
    """
    if not base_url.startswith("http"):
        base_url = f"https://{base_url}"

    robots_url = urljoin(base_url, "/robots.txt")
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(robots_url, headers={"User-Agent": "HermesAudit/1.0"})
            if resp.status_code == 200:
                return resp.text, robots_url
    except Exception as e:
        logger.warning(f"T04: robots.txt fetch failed: {e}")

    return "", robots_url


async def _fetch_sitemap_urls(base_url: str) -> tuple[list[str], list[str], str]:
    """Recupere les URLs des sitemaps.

    Reutilise sitemap_parser.py pour la detection et le parsing BFS.

    Returns: (all_urls, sitemap_urls, source)
    """
    try:
        from hermes.connectors.sitemap_parser import detect_sitemaps, parse_sitemap_recursive

        detected = await detect_sitemaps(base_url)
        if not detected["found"]:
            return [], [], "none"

        sitemap_urls = detected["urls"]
        source = detected["source"]

        urls, _, meta = await parse_sitemap_recursive(
            sitemap_urls, base_url, max_urls=5000, max_depth=3, max_sitemaps=30
        )

        return urls, sitemap_urls, source
    except Exception as e:
        logger.warning(f"T04: sitemap fetch failed: {e}")
        return [], [], "error"


def _analyze_robots_txt(content: str, base_url: str) -> dict:
    """Analyse robots.txt via protego et heuristiques."""
    result = {
        "found": False,
        "size_bytes": len(content),
        "sitemap_refs": [],
        "user_agents": [],
        "disallow_all": False,
        "issues": [],
    }

    if not content.strip():
        result["issues"].append({
            "severity": "high",
            "description": "robots.txt vide ou absent",
            "recommendation": "Creer un fichier robots.txt minimal",
        })
        return result

    result["found"] = True

    try:
        from protego import Protego
        rp = Protego.parse(content)

        # Extraire les sitemaps references
        import re
        sitemap_matches = re.findall(r"(?i)sitemap:\s*(.+)", content)
        result["sitemap_refs"] = [s.strip() for s in sitemap_matches]

        # User-agents mentionnes
        ua_matches = re.findall(r"(?i)user-agent:\s*(.+)", content)
        result["user_agents"] = list(set(ua.strip() for ua in ua_matches))

        # Verifier si tout est bloque
        result["disallow_all"] = not rp.can_fetch("/", "HermesAudit/1.0")

        # Verifier les regles pour Googlebot
        google_allowed = rp.can_fetch("/", "Googlebot")
        if not google_allowed:
            result["issues"].append({
                "severity": "critical",
                "description": "Googlebot est bloque par robots.txt",
                "recommendation": "Ajouter 'User-agent: Googlebot\nAllow: /' dans robots.txt",
            })

    except Exception as e:
        logger.warning(f"T04: protego parse failed: {e}")
        result["issues"].append({
            "severity": "medium",
            "description": f"robots.txt mal forme : {e}",
            "recommendation": "Verifier la syntaxe du fichier robots.txt",
        })

    return result


async def run(state: TechAuditState) -> TechAuditState:
    """Analyse les sitemaps et robots.txt."""
    state.current_agent = "tt04"

    base_url = state.site_url
    if not base_url:
        logger.warning("T04: pas d'URL racine — skip")
        return state

    issue_counter = len(state.issues)

    # 1. Robots.txt
    robots_content, robots_url = await _fetch_robots_txt(base_url)
    state.robots_txt = robots_content
    robots_analysis = _analyze_robots_txt(robots_content, base_url)

    if not robots_analysis["found"]:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="sitemap",
            description="robots.txt absent ou vide",
            url=base_url,
            observed="robots.txt: empty or 404",
            rule="robots.txt present",
            confidence="high",
            source_agent="T04",
            severity="high",
            impact_business="Low",
            gain_potentiel="Medium",
            effort="Creer un robots.txt minimal",
            priority="P2",
        ))

    if robots_analysis["disallow_all"]:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="sitemap",
            description="robots.txt bloque tout (Disallow: /) — le site est invisible pour les moteurs",
            url=robots_url,
            observed="Disallow: /",
            rule="robots.txt ne doit pas tout bloquer",
            confidence="high",
            source_agent="T04",
            severity="critical",
            impact_business="High",
            gain_potentiel="High",
            effort="Modifier robots.txt pour autoriser le crawl",
            priority="P0",
        ))

    for issue in robots_analysis["issues"]:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="sitemap",
            description=issue["description"],
            url=robots_url,
            observed=issue["description"],
            rule="robots.txt valide",
            confidence="high",
            source_agent="T04",
            severity=issue["severity"],
            impact_business="High" if issue["severity"] == "critical" else "Low",
            gain_potentiel="High" if issue["severity"] in ("critical", "high") else "Medium",
            effort="5 min",
            priority="P1" if issue["severity"] in ("critical", "high") else "P2",
        ))

    # 2. Sitemaps
    sitemap_urls, detected_sitemaps, source = await _fetch_sitemap_urls(base_url)
    state.sitemap_urls = sitemap_urls

    if not sitemap_urls:
        issue_counter += 1
        state.issues.append(TechIssue(
            id=f"P-{issue_counter:03d}",
            category="sitemap",
            description="Aucun sitemap detecte",
            url=base_url,
            observed="0 URLs dans les sitemaps",
            rule="sitemap present",
            confidence="high",
            source_agent="T04",
            severity="high",
            impact_business="Medium",
            gain_potentiel="High",
            effort="Creer un sitemap XML et le referencer dans robots.txt",
            priority="P2",
        ))
    else:
        logger.info(f"T04: {len(sitemap_urls)} URLs dans le(s) sitemap(s) (source: {source})")

        # 3. Comparaison sitemap vs crawled
        crawled_urls = {p.url.rstrip("/") for p in state.crawled_pages}
        sitemap_set = {u.rstrip("/") for u in sitemap_urls}

        # URLs dans le sitemap mais non crawlees
        not_crawled = sitemap_set - crawled_urls
        if not_crawled:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="sitemap",
                description=f"{len(not_crawled)} URLs dans le sitemap mais non crawlees",
                url=base_url,
                observed=f"sitemap_urls: {len(sitemap_set)}, crawled: {len(crawled_urls)}, missing: {len(not_crawled)}",
                rule="toutes les URLs du sitemap sont crawlables",
                confidence="high",
                source_agent="T04",
                severity="medium",
                impact_business="Low",
                gain_potentiel="Medium",
                effort="Verifier que ces URLs sont accessibles et indexables",
                priority="P3",
            ))

        # URLs crawlees mais absentes du sitemap
        not_in_sitemap = crawled_urls - sitemap_set
        if not_in_sitemap and len(crawled_urls) > 5:
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="sitemap",
                description=f"{len(not_in_sitemap)} pages crawlees absentes du sitemap",
                url=base_url,
                observed=f"crawled_not_in_sitemap: {len(not_in_sitemap)}",
                rule="toutes les pages indexables sont dans le sitemap",
                confidence="medium",
                source_agent="T04",
                severity="medium",
                impact_business="Medium",
                gain_potentiel="Medium",
                effort="Ajouter ces pages au sitemap si elles sont indexables",
                priority="P3",
            ))

        # Pas de reference au sitemap dans robots.txt
        if robots_analysis["found"] and not robots_analysis["sitemap_refs"] and source != "robots.txt":
            issue_counter += 1
            state.issues.append(TechIssue(
                id=f"P-{issue_counter:03d}",
                category="sitemap",
                description="robots.txt ne reference pas le sitemap",
                url=robots_url,
                observed="Pas de ligne 'Sitemap:' dans robots.txt",
                rule="robots.txt reference le sitemap",
                confidence="high",
                source_agent="T04",
                severity="low",
                impact_business="Low",
                gain_potentiel="Medium",
                effort="Ajouter 'Sitemap: https://...' dans robots.txt",
                priority="P3",
            ))

    logger.info(f"T04: sitemap={len(sitemap_urls)} URLs, robots={'present' if robots_analysis['found'] else 'absent'}")
    state.updated_at = datetime.now()
    return state
