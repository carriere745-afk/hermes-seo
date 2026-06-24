"""Base SQLite pour les Projets — Hermes SEO v3.

Tables :
- projects : un projet = un site client
- project_disclaimers : tracabilite des disclaimers acceptes
- execution_actions : actions executees par le mega-agent P7
- consolidated_recommendations : recommandations unifiees (cross-pipeline)
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger("hermes.project_db")

DB_PATH = Path("data/hermes.db")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            nom TEXT DEFAULT '',
            site_url TEXT NOT NULL,
            domain TEXT NOT NULL,
            profile TEXT DEFAULT 'blog',
            secteur TEXT DEFAULT 'autre',
            competitors TEXT DEFAULT '[]',
            keywords_cibles TEXT DEFAULT '[]',
            budget_mensuel REAL DEFAULT 0.0,
            valeur_lead REAL DEFAULT 100.0,
            taux_conversion REAL DEFAULT 0.02,
            status TEXT DEFAULT 'new',
            onboarding_step TEXT DEFAULT 'welcome',
            onboarding_progress INTEGER DEFAULT 0,
            health_score INTEGER DEFAULT 0,
            content_score INTEGER DEFAULT 0,
            technique_score INTEGER DEFAULT 0,
            visibility_score INTEGER DEFAULT 0,
            strategy_score INTEGER DEFAULT 0,
            authority_score INTEGER DEFAULT 0,
            next_action TEXT DEFAULT '',
            next_pipeline TEXT DEFAULT '',
            next_action_priority TEXT DEFAULT 'P2',
            ymyl_detected INTEGER DEFAULT 0,
            penalite_suspectee INTEGER DEFAULT 0,
            core_update_impacted INTEGER DEFAULT 0,
            pipelines_json TEXT DEFAULT '{}',
            local_seo_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_projects_domain ON projects(domain);
        CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

        CREATE TABLE IF NOT EXISTS project_disclaimers (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            disclaimer_type TEXT NOT NULL,
            disclaimer_id TEXT NOT NULL,
            accepted INTEGER DEFAULT 0,
            accepted_at TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        );
        CREATE INDEX IF NOT EXISTS idx_disclaimers_project ON project_disclaimers(project_id);

        CREATE TABLE IF NOT EXISTS execution_actions (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            source_pipeline TEXT DEFAULT '',
            source_agent TEXT DEFAULT '',
            source_recommandation_id TEXT DEFAULT '',
            category TEXT DEFAULT 'generate',
            action_type TEXT DEFAULT '',
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            priority TEXT DEFAULT 'P2',
            target_url TEXT DEFAULT '',
            target_page TEXT DEFAULT '',
            content_to_generate TEXT DEFAULT '',
            file_to_create TEXT DEFAULT '',
            file_content TEXT DEFAULT '',
            email_template TEXT DEFAULT '',
            params_json TEXT DEFAULT '{}',
            automation_score INTEGER DEFAULT 50,
            conflicts_with TEXT DEFAULT '[]',
            page_to_optimize TEXT DEFAULT '',
            snapshot_before TEXT DEFAULT '{}',
            snapshot_after TEXT DEFAULT '{}',
            execution_cost REAL DEFAULT 0.0,
            human_approval_required INTEGER DEFAULT 0,
            human_approved_at TEXT,
            impact_j7 TEXT DEFAULT '{}',
            impact_j30 TEXT DEFAULT '{}',
            impact_j60 TEXT DEFAULT '{}',
            impact_j90 TEXT DEFAULT '{}',
            confidence_before INTEGER DEFAULT 0,
            confidence_after INTEGER DEFAULT 0,
            correction_factor TEXT DEFAULT '{}',
            created_at TEXT,
            executed_at TEXT,
            execution_result TEXT DEFAULT '',
            execution_error TEXT DEFAULT '',
            predicted_impact TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_ex_actions_project ON execution_actions(project_id);
        CREATE INDEX IF NOT EXISTS idx_ex_actions_status ON execution_actions(status);

        CREATE TABLE IF NOT EXISTS snapshots (
            id TEXT PRIMARY KEY,
            execution_action_id TEXT NOT NULL,
            url TEXT DEFAULT '',
            html_before TEXT DEFAULT '',
            html_after TEXT DEFAULT '',
            diff TEXT DEFAULT '',
            taken_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS patterns (
            id TEXT PRIMARY KEY,
            pattern_id TEXT NOT NULL,
            sector TEXT DEFAULT '',
            profile TEXT DEFAULT '',
            action_type TEXT DEFAULT '',
            context TEXT DEFAULT '{}',
            resultat TEXT DEFAULT '{}',
            occurrences INTEGER DEFAULT 0,
            confidence REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_patterns_sector ON patterns(sector);
        CREATE INDEX IF NOT EXISTS idx_patterns_action ON patterns(action_type);

        CREATE TABLE IF NOT EXISTS failures (
            id TEXT PRIMARY KEY,
            sector TEXT DEFAULT '',
            profile TEXT DEFAULT '',
            action_type TEXT DEFAULT '',
            context TEXT DEFAULT '{}',
            failure_reason TEXT DEFAULT '',
            do_not_recommend_if TEXT DEFAULT '{}',
            occurrences INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_failures_action ON failures(action_type);

        CREATE TABLE IF NOT EXISTS consolidated_recommendations (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            source_pipelines TEXT DEFAULT '[]',
            source_agents TEXT DEFAULT '[]',
            sujet TEXT DEFAULT '',
            description TEXT DEFAULT '',
            action_concrete TEXT DEFAULT '',
            action_executable TEXT DEFAULT '',
            priority TEXT DEFAULT 'P2',
            effort_estime TEXT DEFAULT '',
            cout_estime REAL DEFAULT 0.0,
            impact_estime TEXT DEFAULT '',
            delai_estime TEXT DEFAULT '',
            confidence_score INTEGER DEFAULT 0,
            requires_human INTEGER DEFAULT 0,
            human_reason TEXT DEFAULT '',
            disclaimers_json TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cons_recs_project ON consolidated_recommendations(project_id);
    """)
    conn.commit()
    conn.close()
    logger.info("Project DB initialized (4 tables)")


# ─── Projects CRUD ─────────────────────────────────────────────────────

def create_project(project: dict) -> str:
    pid = project.get("id", uuid4().hex[:12])
    now = datetime.now().isoformat()
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO projects
           (id, nom, site_url, domain, profile, secteur, competitors, keywords_cibles,
            budget_mensuel, valeur_lead, taux_conversion, status, onboarding_step,
            onboarding_progress, health_score, content_score, technique_score,
            visibility_score, strategy_score, authority_score,
            next_action, next_pipeline, next_action_priority,
            ymyl_detected, penalite_suspectee, core_update_impacted,
            pipelines_json, local_seo_json, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid, project.get("nom", ""), project["site_url"], project.get("domain", ""),
         project.get("profile", "blog"), project.get("secteur", "autre"),
         json.dumps(project.get("competitors", [])), json.dumps(project.get("keywords_cibles", [])),
         project.get("budget_mensuel", 0), project.get("valeur_lead", 100),
         project.get("taux_conversion", 0.02), project.get("status", "new"),
         project.get("onboarding_step", "welcome"), project.get("onboarding_progress", 0),
         project.get("health_score", 0), project.get("content_score", 0),
         project.get("technique_score", 0), project.get("visibility_score", 0),
         project.get("strategy_score", 0), project.get("authority_score", 0),
         project.get("next_action", ""), project.get("next_pipeline", ""),
         project.get("next_action_priority", "P2"),
         1 if project.get("ymyl_detected") else 0,
         1 if project.get("penalite_suspectee") else 0,
         1 if project.get("core_update_impacted") else 0,
         json.dumps(project.get("pipelines", {})), json.dumps(project.get("local_seo", {})),
         project.get("created_at", now), now))
    conn.commit()
    conn.close()
    return pid


def get_project(project_id: str = "", domain: str = "") -> dict | None:
    conn = _get_conn()
    if project_id:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    elif domain:
        row = conn.execute("SELECT * FROM projects WHERE domain = ?", (domain,)).fetchone()
    else:
        conn.close()
        return None
    conn.close()
    return dict(row) if row else None


def list_projects(status: str = "") -> list[dict]:
    conn = _get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM projects WHERE status = ? ORDER BY updated_at DESC", (status,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY updated_at DESC LIMIT 50").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_project_scores(project_id: str, scores: dict) -> None:
    conn = _get_conn()
    conn.execute(
        """UPDATE projects SET health_score=?, content_score=?, technique_score=?,
           visibility_score=?, strategy_score=?, authority_score=?,
           next_action=?, next_pipeline=?, next_action_priority=?,
           updated_at=?
           WHERE id=?""",
        (scores.get("health_score", 0), scores.get("content_score", 0),
         scores.get("technique_score", 0), scores.get("visibility_score", 0),
         scores.get("strategy_score", 0), scores.get("authority_score", 0),
         scores.get("next_action", ""), scores.get("next_pipeline", ""),
         scores.get("next_action_priority", "P2"),
         datetime.now().isoformat(), project_id))
    conn.commit()
    conn.close()


# ─── Disclaimers ──────────────────────────────────────────────────────

def accept_disclaimer(project_id: str, disclaimer_type: str) -> None:
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO project_disclaimers
           (id, project_id, disclaimer_type, disclaimer_id, accepted, accepted_at)
           VALUES (?,?,?,?,1,?)""",
        (uuid4().hex[:12], project_id, disclaimer_type, disclaimer_type,
         datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_accepted_disclaimers(project_id: str) -> list[str]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT disclaimer_type FROM project_disclaimers WHERE project_id=? AND accepted=1",
        (project_id,)).fetchall()
    conn.close()
    return [r["disclaimer_type"] for r in rows]


# ─── Execution Actions ────────────────────────────────────────────────

def insert_execution_action(action: dict) -> str:
    aid = action.get("id", uuid4().hex[:12])
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO execution_actions
           (id, project_id, source_pipeline, source_agent, source_recommandation_id,
            category, action_type, description, status, priority,
            target_url, target_page, content_to_generate, file_to_create,
            file_content, email_template, params_json,
            confidence_before, created_at, executed_at,
            execution_result, execution_error, predicted_impact)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (aid, action.get("project_id", ""), action.get("source_pipeline", ""),
         action.get("source_agent", ""), action.get("source_recommandation_id", ""),
         action.get("category", "generate"), action.get("action_type", ""),
         action.get("description", ""), action.get("status", "pending"),
         action.get("priority", "P2"), action.get("target_url", ""),
         action.get("target_page", ""), action.get("content_to_generate", ""),
         action.get("file_to_create", ""), action.get("file_content", ""),
         action.get("email_template", ""), json.dumps(action.get("params", {})),
         action.get("confidence_before", 0), action.get("created_at", datetime.now().isoformat()),
         action.get("executed_at"), action.get("execution_result", ""),
         action.get("execution_error", ""), action.get("predicted_impact", "")))
    conn.commit()
    conn.close()
    return aid


def get_pending_actions(project_id: str) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM execution_actions WHERE project_id=? AND status='pending' "
        "ORDER BY CASE priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END",
        (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Consolidated Recommendations ──────────────────────────────────────

def insert_consolidated_recommendation(rec: dict) -> str:
    rid = rec.get("id", uuid4().hex[:12])
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO consolidated_recommendations
           (id, project_id, source_pipelines, source_agents, sujet, description,
            action_concrete, action_executable, priority, effort_estime, cout_estime,
            impact_estime, delai_estime, confidence_score, requires_human,
            human_reason, disclaimers_json, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (rid, rec.get("project_id", ""), json.dumps(rec.get("source_pipelines", [])),
         json.dumps(rec.get("source_agents", [])), rec.get("sujet", ""),
         rec.get("description", ""), rec.get("action_concrete", ""),
         rec.get("action_executable", ""), rec.get("priority", "P2"),
         rec.get("effort_estime", ""), rec.get("cout_estime", 0),
         rec.get("impact_estime", ""), rec.get("delai_estime", ""),
         rec.get("confidence_score", 0), 1 if rec.get("requires_human") else 0,
         rec.get("human_reason", ""), json.dumps(rec.get("disclaimers", [])),
         datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return rid


# ─── Stats ─────────────────────────────────────────────────────────────

def get_project_stats() -> dict:
    conn = _get_conn()
    stats = {}
    for status in ["new", "onboarding", "active", "stale", "archived", "recovery"]:
        count = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE status=?", (status,)).fetchone()[0]
        stats[status] = count
    total = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    conn.close()
    return {"total": total, "by_status": stats}
