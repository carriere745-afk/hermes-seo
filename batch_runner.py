"""Hermes SEO — Runner batch.

Lance le pipeline sur plusieurs mots-cles depuis un fichier CSV.
Usage: python batch_runner.py mots_cles.csv
"""

import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from hermes.core.session_manager import SessionManager
from hermes.core.workflow import get_active_agents
from hermes.models.common import AgentStatus, QualityMode
from hermes.models.session import SessionConfig, SessionState
from hermes.agents import AGENT_REGISTRY


async def run_one(keyword: str, site_url: str, secteur: str, mode: str,
                  objectif: str = "", dry_run: bool = True) -> SessionState:
    session = SessionState(
        keyword=keyword,
        site_url=site_url or None,
        objectif=objectif or None,
        config=SessionConfig(
            mode=QualityMode(mode),
            dry_run=dry_run,
            secteur=secteur or "autre",
        ),
    )

    active = get_active_agents(
        mode=session.config.mode,
        secteur=session.config.secteur,
        has_existing_content=False,
        has_locale_target=False,
    )

    for agent_id in active:
        if agent_id in AGENT_REGISTRY:
            session.current_agent_id = agent_id
            session = await AGENT_REGISTRY[agent_id](session)

    return session


async def run_batch(input_csv: str, output_dir: str = "sessions",
                    dry_run: bool = True, mode: str = "standard"):
    """Execute le pipeline pour chaque ligne du CSV."""
    manager = SessionManager(Path(output_dir))
    results = []

    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    print(f"Hermes SEO Batch — {total} articles a generer")
    print(f"Mode: {'essai (dry-run)' if dry_run else 'REEL (appels API)'}")
    print(f"Qualite: {mode}")
    print("-" * 60)

    for i, row in enumerate(rows, 1):
        keyword = row.get("keyword", "").strip()
        if not keyword:
            continue

        site_url = row.get("site_url", "").strip()
        secteur = row.get("secteur", "autre").strip()
        objectif = row.get("objectif", "").strip()

        print(f"\n[{i}/{total}] '{keyword}' ...", end=" ", flush=True)
        start = datetime.now()

        try:
            session = await run_one(
                keyword=keyword,
                site_url=site_url,
                secteur=secteur,
                mode=mode,
                objectif=objectif,
                dry_run=dry_run,
            )
            elapsed = (datetime.now() - start).total_seconds()
            score = (session.scores or {}).get("score_total", "?")
            print(f"OK ({elapsed:.0f}s, score={score}/100)")

            manager.save(session)
            results.append({
                "keyword": keyword,
                "session_id": session.session_id,
                "score": score,
                "status": "ok",
            })
        except Exception as e:
            print(f"ECHEC: {e}")
            results.append({
                "keyword": keyword,
                "status": f"erreur: {e}",
            })

    print("\n" + "=" * 60)
    ok = sum(1 for r in results if r.get("status") == "ok")
    print(f"Termine : {ok}/{total} articles generes avec succes.")
    if ok < total:
        failed = [r for r in results if r.get("status") != "ok"]
        for f in failed:
            print(f"  ❌ {f['keyword']}: {f['status']}")

    # Sauvegarder le rapport
    report_path = Path(output_dir) / f"batch_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(report_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["keyword", "session_id", "score", "status"])
        writer.writeheader()
        writer.writerows(results)
    print(f"Rapport: {report_path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Hermes SEO Batch Runner")
    parser.add_argument("csv_file", help="Fichier CSV (colonnes: keyword, site_url, secteur, objectif)")
    parser.add_argument("--output", "-o", default="sessions", help="Dossier de sortie")
    parser.add_argument("--real", action="store_true", help="Mode reel (appels API)")
    parser.add_argument("--mode", "-m", default="standard",
                       choices=["fast", "standard", "premium", "compliance", "debug"])
    args = parser.parse_args()

    asyncio.run(run_batch(
        input_csv=args.csv_file,
        output_dir=args.output,
        dry_run=not args.real,
        mode=args.mode,
    ))
