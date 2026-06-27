"""Mode headless — Executer les pipelines sans Streamlit.

Usage:
    python -m hermes.headless --pipeline=p4 --site=https://example.com --keywords="kw1,kw2"
    python -m hermes.headless --pipeline=all --site=https://example.com
    python -m hermes.headless --pipeline=p4 --cron  # Lance P4 en boucle (pour cron/VPS)

Utilise pour:
- Cron jobs (P4 quotidien/hebdo)
- API REST (endpoint /api/audit)
- Tests CI/CD
- Deploiement VPS sans interface graphique
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("hermes.headless")


async def run_pipeline(pipeline: str, site_url: str, keywords: list[str],
                       competitors: list[str], mode: str = "standard",
                       profile: str = "blog", domain: str = "") -> dict:
    """Execute un pipeline specifique en mode headless."""
    t0 = time.perf_counter()
    result = {"pipeline": pipeline, "site": site_url, "timestamp": datetime.now().isoformat()}

    if not site_url.startswith("http"):
        return {"error": "URL invalide", **result}

    if not domain:
        from urllib.parse import urlparse
        domain = urlparse(site_url).netloc.replace("www.", "")

    try:
        if pipeline in ("p4", "serp", "all"):
            from hermes.models.serp_visibility import SerpVisibilityState
            from hermes.agents.serp_visibility import SERP_ORDER, SERP_REGISTRY
            state = SerpVisibilityState(site_url=site_url, keywords=keywords,
                                        competitors=competitors, mode=mode)
            for aid in SERP_ORDER:
                if aid in SERP_REGISTRY:
                    state = await SERP_REGISTRY[aid](state)
            result["p4"] = {"health": state.health_score, "positions": len(state.positions),
                            "quick_wins": len(state.quick_wins), "alerts": len(state.alerts)}

        if pipeline in ("p5", "strategie", "all"):
            from hermes.models.strategie import StrategieState
            from hermes.agents.strategie import STRATEGIE_ORDER, STRATEGIE_REGISTRY
            state = StrategieState(site_url=site_url, domain=domain, mode=mode,
                                   profile=profile, keywords_monitored=keywords,
                                   competitors=competitors)
            for aid in STRATEGIE_ORDER:
                if aid in STRATEGIE_REGISTRY:
                    state = await STRATEGIE_REGISTRY[aid](state)
            es = state.executive_summary
            result["p5"] = {"sante": es.sante_strategique if es else 0,
                            "sujets": len(state.sujets), "recos": len(state.recommandations),
                            "kill_list": len(state.kill_list)}

        if pipeline in ("p6", "backlinks", "all"):
            from hermes.models.backlinks import BacklinksState
            from hermes.agents.backlinks import BACKLINKS_ORDER, BACKLINKS_REGISTRY
            state = BacklinksState(site_url=site_url, domain=domain, mode=mode,
                                   profile=profile, competitors=competitors,
                                   keywords_cibles=keywords[:8] if keywords else [])
            for aid in BACKLINKS_ORDER:
                if aid in BACKLINKS_REGISTRY:
                    state = await BACKLINKS_REGISTRY[aid](state)
            result["p6"] = {"auth": state.authority_score, "health": state.link_profile_health,
                            "backlinks": len(state.backlinks), "recos": len(state.recommandations)}

        if pipeline in ("p7", "maintenance", "all"):
            from hermes.models.project import Project
            from hermes.core.project_db import create_project, get_project, init_db
            from hermes.agents.maintenance import MAINTENANCE_ORDER, MAINTENANCE_REGISTRY
            init_db()
            existing = get_project(domain=domain)
            pid = existing["id"] if existing else create_project({
                "nom": domain, "site_url": site_url, "domain": domain,
                "profile": profile, "secteur": "autre",
                "competitors": competitors, "keywords_cibles": keywords,
            })
            project = Project(id=pid, nom=domain, site_url=site_url, domain=domain,
                             profile=profile, secteur="autre", mode_execution="semi-auto")
            for aid in MAINTENANCE_ORDER:
                if aid in MAINTENANCE_REGISTRY:
                    project = await MAINTENANCE_REGISTRY[aid](project)
            result["p7"] = {"actions": len(project.execution_actions),
                            "executed": sum(1 for a in project.execution_actions if a.status == "executed")}

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Pipeline {pipeline} failed: {e}")

    result["duration_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


def main():
    parser = argparse.ArgumentParser(description="Hermes SEO — Mode headless")
    parser.add_argument("--pipeline", "-p", default="all",
                       choices=["p4","p5","p6","p7","all","serp","strategie","backlinks","maintenance"],
                       help="Pipeline a executer (defaut: all)")
    parser.add_argument("--site", "-s", required=True, help="URL du site")
    parser.add_argument("--keywords", "-k", default="", help="Mots-cles (separes par des virgules)")
    parser.add_argument("--competitors", "-c", default="", help="Concurrents (separes par des virgules)")
    parser.add_argument("--mode", "-m", default="standard", choices=["fast","standard","premium"])
    parser.add_argument("--profile", default="blog", choices=["blog","ecommerce","saas","local","corporate"])
    parser.add_argument("--cron", action="store_true", help="Mode cron: boucle infinie (P4 quotidien)")
    parser.add_argument("--output", "-o", help="Fichier JSON de sortie")
    parser.add_argument("--quiet", "-q", action="store_true", help="Pas de log sauf erreurs")

    args = parser.parse_args()
    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    competitors = [c.strip() for c in args.competitors.split(",") if c.strip()]

    async def run():
        if args.cron:
            logger.info(f"Mode cron: P4 toutes les 24h pour {args.site}")
            while True:
                result = await run_pipeline("p4", args.site, keywords, competitors, args.mode, args.profile)
                logger.info(f"Cron cycle: health={result.get('p4',{}).get('health','?')}/100")
                if args.output:
                    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False))
                await asyncio.sleep(86400)  # 24h
        else:
            result = await run_pipeline(args.pipeline, args.site, keywords, competitors, args.mode, args.profile)
            out = json.dumps(result, indent=2, ensure_ascii=False)
            if args.output:
                Path(args.output).write_text(out)
                logger.info(f"Resultat sauvegarde: {args.output}")
            else:
                print(out)
            if "error" in result:
                sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    main()
