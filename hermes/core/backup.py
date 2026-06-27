"""Backup automatique des bases SQLite Hermes SEO.

Usage:
    python -m hermes.core.backup  # Backup toutes les DBs
    python -m hermes.core.backup --vacuum  # VACUUM + backup

Execute automatiquement avant chaque operation critique.
Les backups sont horodates et conserves 30 jours.
"""

import logging
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("hermes.backup")

BACKUP_DIR = Path("data/backups")
MAX_BACKUP_AGE_DAYS = 30

DBS = ["serp_visibility.db", "strategie.db", "backlinks.db", "hermes.db"]


def backup_all(vacuum: bool = False) -> dict:
    """Backup toutes les DBs. Retourne {db_name: backup_path}."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {}

    for db_name in DBS:
        db_path = Path("data") / db_name
        if not db_path.exists():
            continue

        backup_path = BACKUP_DIR / f"{now}_{db_name}"

        if vacuum:
            try:
                conn = sqlite3.connect(str(db_path))
                conn.execute("VACUUM")
                conn.close()
            except Exception as e:
                logger.warning(f"VACUUM failed for {db_name}: {e}")

        try:
            shutil.copy2(str(db_path), str(backup_path))
            results[db_name] = str(backup_path)
        except Exception as e:
            logger.error(f"Backup failed for {db_name}: {e}")

    # Cleanup vieux backups
    _cleanup_old_backups()

    if results:
        logger.info(f"Backup: {len(results)} DBs sauvegardees dans {BACKUP_DIR}")
    return results


def _cleanup_old_backups():
    """Supprime les backups de plus de MAX_BACKUP_AGE_DAYS jours."""
    if not BACKUP_DIR.exists():
        return
    cutoff = datetime.now() - timedelta(days=MAX_BACKUP_AGE_DAYS)
    for f in BACKUP_DIR.iterdir():
        if f.is_file() and f.name.endswith(".db"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                f.unlink()
                logger.debug(f"Backup cleaned: {f.name}")


def restore_latest(db_name: str) -> bool:
    """Restaure le backup le plus recent d'une DB."""
    if not BACKUP_DIR.exists():
        return False
    backups = sorted(BACKUP_DIR.glob(f"*_{db_name}"), reverse=True)
    if not backups:
        return False
    target = Path("data") / db_name
    shutil.copy2(str(backups[0]), str(target))
    logger.info(f"Restore: {db_name} depuis {backups[0].name}")
    return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import sys
    vacuum = "--vacuum" in sys.argv
    results = backup_all(vacuum=vacuum)
    for db, path in results.items():
        print(f"  {db} -> {path}")
    print(f"Backup termine: {len(results)} DBs")
