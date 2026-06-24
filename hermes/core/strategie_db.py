"""Base SQLite pour le Pipeline 5 — Strategie + Observability Layer.

Tables :
- hermes_events : journalisation de chaque agent (tous pipelines)
- predictions_history : suivi des predictions pour le futur Learning Engine
- strategie_sessions : etat des sessions de strategie
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

logger = logging.getLogger("hermes.strategie_db")

DB_PATH = Path("data/strategie.db")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS hermes_events (
            event_id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            session_id TEXT NOT NULL,
            pipeline_id TEXT NOT NULL DEFAULT 'strategie',
            agent_id TEXT NOT NULL,
            model TEXT DEFAULT 'none',
            tokens_used INTEGER DEFAULT 0,
            cost REAL DEFAULT 0.0,
            duration_ms INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            error TEXT DEFAULT '',
            predictions TEXT DEFAULT '{}',
            confidence REAL DEFAULT 0.0,
            trace TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_events_session ON hermes_events(session_id);
        CREATE INDEX IF NOT EXISTS idx_events_pipeline ON hermes_events(pipeline_id);
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON hermes_events(timestamp);

        CREATE TABLE IF NOT EXISTS predictions_history (
            prediction_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            pipeline_id TEXT NOT NULL DEFAULT 'strategie',
            agent_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            url TEXT DEFAULT '',
            keyword TEXT DEFAULT '',
            predicted_traffic INTEGER DEFAULT 0,
            predicted_leads INTEGER DEFAULT 0,
            predicted_roi REAL DEFAULT 0.0,
            confidence REAL DEFAULT 0.0,
            date_prediction TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_predictions_session ON predictions_history(session_id);
        CREATE INDEX IF NOT EXISTS idx_predictions_date ON predictions_history(date_prediction);

        CREATE TABLE IF NOT EXISTS strategie_sessions (
            session_id TEXT PRIMARY KEY,
            site_url TEXT DEFAULT '',
            domain TEXT DEFAULT '',
            mode TEXT DEFAULT 'standard',
            status TEXT DEFAULT 'created',
            phase TEXT DEFAULT 'startup',
            current_agent TEXT DEFAULT '',
            recommendations_count INTEGER DEFAULT 0,
            kill_list_count INTEGER DEFAULT 0,
            health_score INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            state_json TEXT DEFAULT '{}'
        );
    """)
    conn.commit()
    conn.close()
    logger.info("Strategie DB initialized")


# ─── Hermes Events ─────────────────────────────────────────────────────

def log_event(
    session_id: str,
    agent_id: str,
    pipeline_id: str = "strategie",
    model: str = "none",
    tokens_used: int = 0,
    cost: float = 0.0,
    duration_ms: int = 0,
    success: bool = True,
    error: str = "",
    predictions: Optional[dict] = None,
    confidence: float = 0.0,
    trace: Optional[dict] = None,
) -> str:
    event_id = uuid4().hex[:12]
    conn = _get_conn()
    conn.execute(
        """INSERT INTO hermes_events
           (event_id, timestamp, session_id, pipeline_id, agent_id, model,
            tokens_used, cost, duration_ms, success, error, predictions, confidence, trace)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (event_id, datetime.now().isoformat(), session_id, pipeline_id, agent_id,
         model, tokens_used, cost, duration_ms, 1 if success else 0, error,
         json.dumps(predictions or {}), confidence, json.dumps(trace or {})))
    conn.commit()
    conn.close()
    return event_id


def get_pipeline_stats(pipeline_id: str = "strategie", days: int = 30) -> dict:
    conn = _get_conn()
    row = conn.execute(
        """SELECT COUNT(*) as total_runs, SUM(tokens_used) as total_tokens,
                  SUM(cost) as total_cost, SUM(duration_ms) as total_duration_ms,
                  AVG(CASE WHEN success=1 THEN 1.0 ELSE 0.0 END) as success_rate
           FROM hermes_events
           WHERE pipeline_id = ? AND timestamp >= date('now', ?)""",
        (pipeline_id, f"-{days} days")).fetchone()
    conn.close()
    return dict(row) if row else {}


def get_session_events(session_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM hermes_events WHERE session_id = ? ORDER BY timestamp",
        (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Predictions ────────────────────────────────────────────────────────

def save_prediction(
    session_id: str,
    agent_id: str,
    action_type: str,
    pipeline_id: str = "strategie",
    url: str = "",
    keyword: str = "",
    predicted_traffic: int = 0,
    predicted_leads: int = 0,
    predicted_roi: float = 0.0,
    confidence: float = 0.0,
) -> str:
    prediction_id = uuid4().hex[:12]
    conn = _get_conn()
    conn.execute(
        """INSERT INTO predictions_history
           (prediction_id, session_id, pipeline_id, agent_id, action_type,
            url, keyword, predicted_traffic, predicted_leads, predicted_roi,
            confidence, date_prediction)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (prediction_id, session_id, pipeline_id, agent_id, action_type,
         url, keyword, predicted_traffic, predicted_leads, predicted_roi,
         confidence, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return prediction_id


def get_predictions_for_session(session_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM predictions_history WHERE session_id = ? ORDER BY date_prediction",
        (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Sessions Strategie ─────────────────────────────────────────────────

def save_session_state(session_id: str, state_json: str, status: str = "running",
                       phase: str = "startup", current_agent: str = "",
                       recs: int = 0, kills: int = 0, health: int = 0,
                       site_url: str = "", domain: str = "", mode: str = "standard") -> None:
    conn = _get_conn()
    now = datetime.now().isoformat()
    # Verifier si la session existe deja
    existing = conn.execute(
        "SELECT created_at FROM strategie_sessions WHERE session_id=?",
        (session_id,)).fetchone()
    created = existing["created_at"] if existing else now
    conn.execute(
        """INSERT OR REPLACE INTO strategie_sessions
           (session_id, site_url, domain, mode, status, phase, current_agent,
            recommendations_count, kill_list_count, health_score,
            created_at, updated_at, state_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (session_id, site_url, domain, mode, status, phase, current_agent,
         recs, kills, health, created, now, state_json))
    conn.commit()
    conn.close()


def get_db_stats() -> dict:
    conn = _get_conn()
    tables = ["hermes_events", "predictions_history", "strategie_sessions"]
    stats = {}
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        stats[t] = count
    conn.close()
    return stats
