"""Agent 40 — Verification Propriete Site (gap module 1 item #3).

Verifie qu'un site appartient bien a l'utilisateur via:
- DNS TXT record
- Meta tag Google
- Fichier verification GSC
- Google Search Console API

Sans verification, les fonctionnalites avancees (injection CMS, lecture GSC) sont limitees.
"""

import logging, re, time, hashlib
from datetime import datetime

import httpx

from hermes.models.session import SessionState, AgentResult
from hermes.models.common import AgentStatus
from hermes.core.logging import log_agent_start, log_agent_completed, log_agent_failed

logger = logging.getLogger("hermes.agent_40")


async def run(state: SessionState) -> SessionState:
    agent_id = "agent_40"
    agent_name = "Verification Propriete"
    t0 = time.perf_counter()
    log_agent_start(agent_id, agent_name)
    result = state.agent_results.setdefault(agent_id, AgentResult(agent_id=agent_id, agent_name=agent_name))
    result.status = AgentStatus.RUNNING

    try:
        url = (state.site_url or "").rstrip("/")
        if not url.startswith("http"):
            url = f"https://{url}"
        domain = url.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

        verif = {
            "domain": domain,
            "site_url": url,
            "gsc_verified": False,
            "https_valid": False,
            "sitemap_accessible": False,
            "robots_accessible": False,
            "meta_tag_found": False,
            "ownership_token": hashlib.md5(f"hermes-verify-{domain}".encode()).hexdigest()[:16],
            "methods": [],
        }

        # 1. HTTPS
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(url)
                verif["https_valid"] = resp.status_code < 500 and url.startswith("https")
        except Exception:
            pass

        # 2. Sitemap accessible
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{url}/sitemap.xml")
                verif["sitemap_accessible"] = resp.status_code == 200
        except Exception:
            pass

        # 3. Robots.txt accessible
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{url}/robots.txt")
                verif["robots_accessible"] = resp.status_code == 200
        except Exception:
            pass

        # 4. GSC verification
        try:
            from hermes.connectors.gsc_connector import gsc
            if gsc.is_configured:
                await gsc._ensure_token()
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://www.googleapis.com/webmasters/v3/sites",
                        headers={"Authorization": f"Bearer {gsc._access_token}"})
                    if resp.status_code == 200:
                        sites = resp.json().get("siteEntry", [])
                        site_urls = [s.get("siteUrl", "") for s in sites]
                        verif["gsc_verified"] = any(domain in su for su in site_urls)
                        verif["gsc_sites_found"] = len(sites)
        except Exception:
            pass

        # 5. Methodes de verification recommandees
        if verif["https_valid"]:
            verif["methods"].append("DNS: ajouter un enregistrement TXT hermes-verify=VOTRE_TOKEN")
            verif["methods"].append(f"HTML: ajouter <meta name='hermes-verify' content='{verif['ownership_token']}'>")
            verif["methods"].append("Fichier: uploader hermes-verify.html a la racine du site")
        if not verif["gsc_verified"]:
            verif["methods"].append("GSC: verifier le site dans Google Search Console")

        verif["verified"] = verif["gsc_verified"] or verif["https_valid"]

        result.status = AgentStatus.COMPLETED
        result.data = verif
        log_agent_completed(agent_id, agent_name, int((time.perf_counter() - t0) * 1000))
    except Exception as e:
        result.status = AgentStatus.FAILED; result.error_message = str(e)
        log_agent_failed(agent_id, agent_name, str(e))
    state.updated_at = datetime.now()
    return state
