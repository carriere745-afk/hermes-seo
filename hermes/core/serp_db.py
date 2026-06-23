"""Base SQLite pour le Pipeline 4 — SERP & Visibility Intelligence.

Stocke l'historique des positions, alertes, share of voice, AI visibility,
correlations et actions_log pour le suivi temporel.

Tables :
- positions_history : chaque point de donnee (url, keyword, position, date)
- alerts_log : historique des alertes
- competitor_positions : positions concurrents
- share_of_voice : SOV hebdomadaire
- ai_visibility : citations IA
- actions_log : actions Hermes (P1/P3/P7)
- correlations : correlations actions → positions
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("hermes.serp_db")

DB_PATH = Path("data/serp_visibility.db")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    """Initialise le schema SQLite."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS positions_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            keyword TEXT NOT NULL,
            position INTEGER,
            position_previous INTEGER DEFAULT 0,
            variation INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            ctr REAL DEFAULT 0.0,
            search_volume INTEGER DEFAULT 0,
            device TEXT DEFAULT 'mobile',
            source TEXT DEFAULT 'GSC',
            date TEXT NOT NULL,
            url_classee TEXT DEFAULT '',
            featured_snippet INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_positions_keyword ON positions_history(keyword);
        CREATE INDEX IF NOT EXISTS idx_positions_date ON positions_history(date);
        CREATE INDEX IF NOT EXISTS idx_positions_url ON positions_history(url);

        CREATE TABLE IF NOT EXISTS alerts_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            keyword TEXT DEFAULT '',
            url TEXT DEFAULT '',
            valeur_avant REAL,
            valeur_apres REAL,
            priorite TEXT DEFAULT 'P2',
            canal TEXT DEFAULT 'UI',
            statut TEXT DEFAULT 'ouvert',
            date TEXT NOT NULL,
            note TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS competitor_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            keyword TEXT NOT NULL,
            position INTEGER,
            url TEXT DEFAULT '',
            date TEXT NOT NULL,
            source TEXT DEFAULT 'DataForSEO'
        );

        CREATE TABLE IF NOT EXISTS share_of_voice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            date TEXT NOT NULL,
            sov_impressions REAL DEFAULT 0.0,
            sov_clicks REAL DEFAULT 0.0,
            weighted_visibility REAL DEFAULT 0.0,
            evolution_7d REAL DEFAULT 0.0,
            evolution_30d REAL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS ai_visibility (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT NOT NULL,
            source_ia TEXT NOT NULL,
            cited_url TEXT DEFAULT '',
            citation_context TEXT DEFAULT '',
            confidence TEXT DEFAULT 'medium',
            date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS actions_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            url TEXT NOT NULL,
            pipeline_source TEXT DEFAULT '',
            date TEXT NOT NULL,
            details TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS correlations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_id INTEGER,
            url TEXT NOT NULL,
            keyword TEXT NOT NULL,
            delta_j7 INTEGER DEFAULT 0,
            delta_j30 INTEGER DEFAULT 0,
            delta_j60 INTEGER DEFAULT 0,
            delta_j90 INTEGER DEFAULT 0,
            confidence_score TEXT DEFAULT 'Low',
            pattern TEXT DEFAULT ''
        );
    """)
    conn.commit()
    conn.close()
    logger.info("SerpVisibility DB initialized")


# ─── Positions ────────────────────────────────────────────────────────

def insert_position(entry: dict) -> int:
    conn = _get_conn()
    c = conn.execute(
        """INSERT INTO positions_history
           (url, keyword, position, position_previous, variation,
            impressions, clicks, ctr, search_volume, device, source, date, url_classee, featured_snippet)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (entry["url"], entry["keyword"], entry["position"],
         entry.get("position_previous", 0), entry.get("variation", 0),
         entry.get("impressions", 0), entry.get("clicks", 0), entry.get("ctr", 0.0),
         entry.get("search_volume", 0), entry.get("device", "mobile"),
         entry.get("source", "GSC"), entry.get("date", datetime.now().isoformat()),
         entry.get("url_classee", ""), 1 if entry.get("featured_snippet") else 0))
    conn.commit()
    rowid = c.lastrowid
    conn.close()
    return rowid


def insert_positions_batch(entries: list[dict]) -> int:
    conn = _get_conn()
    count = 0
    for entry in entries:
        conn.execute(
            """INSERT INTO positions_history
               (url, keyword, position, position_previous, variation,
                impressions, clicks, ctr, search_volume, device, source, date)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (entry["url"], entry["keyword"], entry["position"],
             entry.get("position_previous", 0), entry.get("variation", 0),
             entry.get("impressions", 0), entry.get("clicks", 0), entry.get("ctr", 0.0),
             entry.get("search_volume", 0), entry.get("device", "mobile"),
             entry.get("source", "GSC"), entry.get("date", datetime.now().isoformat())))
        count += 1
    conn.commit()
    conn.close()
    return count


def get_positions_for_keyword(keyword: str, days: int = 90) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT * FROM positions_history
           WHERE keyword = ? AND date >= date('now', ?)
           ORDER BY date DESC""",
        (keyword, f"-{days} days")).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_positions_summary(days: int = 7) -> list[dict]:
    """Top keywords avec position, variation, impressions sur N jours."""
    conn = _get_conn()
    rows = conn.execute(
        """SELECT keyword, url, AVG(position) as avg_pos,
                  SUM(impressions) as total_imp, SUM(clicks) as total_clicks,
                  MAX(position) - MIN(position) as variation
           FROM positions_history
           WHERE date >= date('now', ?)
           GROUP BY keyword, url
           ORDER BY total_imp DESC
           LIMIT 100""",
        (f"-{days} days",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Alertes ───────────────────────────────────────────────────────────

def insert_alert(entry: dict) -> int:
    conn = _get_conn()
    c = conn.execute(
        """INSERT INTO alerts_log (type, keyword, url, valeur_avant, valeur_apres, priorite, canal, statut, date, note)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (entry["type"], entry.get("keyword", ""), entry.get("url", ""),
         entry.get("valeur_avant"), entry.get("valeur_apres"),
         entry.get("priorite", "P2"), entry.get("canal", "UI"),
         entry.get("statut", "ouvert"), entry.get("date", datetime.now().isoformat()),
         entry.get("note", "")))
    conn.commit()
    rowid = c.lastrowid
    conn.close()
    return rowid


# ─── Actions ───────────────────────────────────────────────────────────

def log_action(entry: dict) -> int:
    conn = _get_conn()
    c = conn.execute(
        """INSERT INTO actions_log (type, url, pipeline_source, date, details)
           VALUES (?,?,?,?,?)""",
        (entry["type"], entry["url"], entry.get("pipeline_source", ""),
         entry.get("date", datetime.now().isoformat()), entry.get("details", "")))
    conn.commit()
    rowid = c.lastrowid
    conn.close()
    return rowid


def get_actions_since(days: int = 90) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM actions_log WHERE date >= date('now', ?) ORDER BY date DESC",
        (f"-{days} days",)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Correlations ──────────────────────────────────────────────────────

def insert_correlation(entry: dict) -> int:
    conn = _get_conn()
    c = conn.execute(
        """INSERT INTO correlations (action_id, url, keyword, delta_j7, delta_j30, delta_j60, delta_j90, confidence_score, pattern)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (entry["action_id"], entry["url"], entry["keyword"],
         entry.get("delta_j7", 0), entry.get("delta_j30", 0),
         entry.get("delta_j60", 0), entry.get("delta_j90", 0),
         entry.get("confidence_score", "Low"), entry.get("pattern", "")))
    conn.commit()
    rowid = c.lastrowid
    conn.close()
    return rowid


def get_db_stats() -> dict:
    conn = _get_conn()
    tables = ["positions_history", "alerts_log", "competitor_positions", "share_of_voice", "ai_visibility", "actions_log", "correlations"]
    stats = {}
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        stats[t] = count
    conn.close()
    return stats
