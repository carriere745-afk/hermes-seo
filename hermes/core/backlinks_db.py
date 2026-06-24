"""Base SQLite pour le Pipeline 6 — Maillage & Backlinks.

Tables :
- backlinks : historique des backlinks
- referring_domains : metriques par domaine referent
- toxic_domains : domaines detectes comme toxiques
- backlink_opportunities : opportunites identifiees
- campaigns : CRM campagnes de netlinking
- campaign_results : resultats B08 (prepares des MVP)
- entity_mentions : B16
- media_relationships : B17
- portfolio_snapshots : B15
- anchor_profiles : profils d'ancres
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger("hermes.backlinks_db")

DB_PATH = Path("data/backlinks.db")


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS backlinks (
            id TEXT PRIMARY KEY,
            source_url TEXT NOT NULL,
            source_domain TEXT NOT NULL,
            target_url TEXT NOT NULL,
            anchor_text TEXT DEFAULT '',
            anchor_type TEXT DEFAULT 'generic',
            link_type TEXT DEFAULT 'editorial',
            is_dofollow INTEGER DEFAULT 1,
            is_lost INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            source_dr REAL DEFAULT 0.0,
            source_traffic INTEGER DEFAULT 0,
            source_keywords_count INTEGER DEFAULT 0,
            toxicity_score REAL DEFAULT 0.0,
            toxicity_level TEXT DEFAULT 'safe',
            confidence TEXT DEFAULT 'medium',
            session_id TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_bl_domain ON backlinks(source_domain);
        CREATE INDEX IF NOT EXISTS idx_bl_target ON backlinks(target_url);
        CREATE INDEX IF NOT EXISTS idx_bl_type ON backlinks(link_type);

        CREATE TABLE IF NOT EXISTS referring_domains (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL UNIQUE,
            domain_rating REAL DEFAULT 0.0,
            topical_score REAL DEFAULT 0.0,
            link_scarcity REAL DEFAULT 0.0,
            geo_relevance REAL DEFAULT 0.0,
            backlinks_count INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT,
            domain_type TEXT DEFAULT 'blog',
            country TEXT DEFAULT '',
            language TEXT DEFAULT 'fr',
            is_competitor INTEGER DEFAULT 0,
            trust_flow REAL DEFAULT 0.0,
            citation_flow REAL DEFAULT 0.0,
            session_id TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_rd_domain ON referring_domains(domain);
        CREATE INDEX IF NOT EXISTS idx_rd_rating ON referring_domains(domain_rating);

        CREATE TABLE IF NOT EXISTS toxic_domains (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            reason TEXT DEFAULT '',
            toxicity_score REAL DEFAULT 0.0,
            patterns_detected TEXT DEFAULT '',
            detected_at TEXT NOT NULL,
            session_id TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS backlink_opportunities (
            id TEXT PRIMARY KEY,
            domain TEXT NOT NULL,
            url TEXT DEFAULT '',
            contact_email TEXT DEFAULT '',
            contact_name TEXT DEFAULT '',
            domain_rating REAL DEFAULT 0.0,
            topical_score REAL DEFAULT 0.0,
            opportunity_type TEXT DEFAULT 'guest_post',
            priority TEXT DEFAULT 'P2',
            impact_score REAL DEFAULT 0.0,
            feasibility_score REAL DEFAULT 0.0,
            cost_estime REAL DEFAULT 0.0,
            effort_estime TEXT DEFAULT '2h',
            roi_estime REAL DEFAULT 0.0,
            status TEXT DEFAULT 'prospect',
            source TEXT DEFAULT '',
            description TEXT DEFAULT '',
            keywords_cibles TEXT DEFAULT '[]',
            session_id TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_opp_status ON backlink_opportunities(status);
        CREATE INDEX IF NOT EXISTS idx_opp_priority ON backlink_opportunities(priority);

        CREATE TABLE IF NOT EXISTS campaigns (
            id TEXT PRIMARY KEY,
            opportunity_id TEXT DEFAULT '',
            domain TEXT NOT NULL,
            contact_name TEXT DEFAULT '',
            contact_email TEXT DEFAULT '',
            contact_role TEXT DEFAULT '',
            status TEXT DEFAULT 'prospect',
            last_contact_date TEXT,
            next_followup_date TEXT,
            followup_count INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            email_thread_id TEXT DEFAULT '',
            cost_engaged REAL DEFAULT 0.0,
            link_acquired INTEGER DEFAULT 0,
            acquired_date TEXT,
            acquired_url TEXT DEFAULT '',
            relationship_score REAL DEFAULT 0.0,
            session_id TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_camp_status ON campaigns(status);
        CREATE INDEX IF NOT EXISTS idx_camp_followup ON campaigns(next_followup_date);

        CREATE TABLE IF NOT EXISTS campaign_results (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            backlink_id TEXT DEFAULT '',
            acquisition_date TEXT,
            cost REAL DEFAULT 0.0,
            link_type TEXT DEFAULT '',
            target_page TEXT DEFAULT '',
            position_at_acquisition REAL DEFAULT 0.0,
            traffic_at_acquisition REAL DEFAULT 0.0,
            ranking_change_j30 REAL DEFAULT 0.0,
            ranking_change_j60 REAL DEFAULT 0.0,
            ranking_change_j90 REAL DEFAULT 0.0,
            traffic_change_j30 REAL DEFAULT 0.0,
            traffic_change_j60 REAL DEFAULT 0.0,
            traffic_change_j90 REAL DEFAULT 0.0,
            confidence_score REAL DEFAULT 0.0,
            captured_at TEXT
        );

        CREATE TABLE IF NOT EXISTS entity_mentions (
            id TEXT PRIMARY KEY,
            entity_name TEXT NOT NULL,
            entity_type TEXT DEFAULT 'brand',
            source_url TEXT DEFAULT '',
            source_authority REAL DEFAULT 0.0,
            context TEXT DEFAULT '',
            sentiment TEXT DEFAULT 'neutral',
            has_link INTEGER DEFAULT 0,
            detected_at TEXT NOT NULL,
            session_id TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_em_entity ON entity_mentions(entity_name);

        CREATE TABLE IF NOT EXISTS media_relationships (
            id TEXT PRIMARY KEY,
            media_domain TEXT NOT NULL,
            contact_email TEXT DEFAULT '',
            contact_name TEXT DEFAULT '',
            total_contacts INTEGER DEFAULT 0,
            total_responses INTEGER DEFAULT 0,
            total_publications INTEGER DEFAULT 0,
            avg_response_time_days REAL DEFAULT 0.0,
            relationship_score REAL DEFAULT 0.0,
            last_contact TEXT,
            session_id TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id TEXT PRIMARY KEY,
            media_national_ratio REAL DEFAULT 0.0,
            media_sectoriel_ratio REAL DEFAULT 0.0,
            blogs_experts_ratio REAL DEFAULT 0.0,
            annuaires_ratio REAL DEFAULT 0.0,
            associations_ratio REAL DEFAULT 0.0,
            partenariats_ratio REAL DEFAULT 0.0,
            podcasts_ratio REAL DEFAULT 0.0,
            communautes_ratio REAL DEFAULT 0.0,
            target_mix TEXT DEFAULT '{}',
            captured_at TEXT NOT NULL,
            session_id TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS anchor_profiles (
            id TEXT PRIMARY KEY,
            session_id TEXT DEFAULT '',
            anchor_type TEXT NOT NULL,
            current_ratio REAL DEFAULT 0.0,
            target_ratio REAL DEFAULT 0.0,
            risk_flag INTEGER DEFAULT 0,
            captured_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    logger.info("Backlinks DB initialized (10 tables)")


# ─── Backlinks CRUD ────────────────────────────────────────────────────

def insert_backlinks_batch(entries: list[dict]) -> int:
    conn = _get_conn()
    count = 0
    for e in entries:
        conn.execute(
            """INSERT OR REPLACE INTO backlinks
               (id, source_url, source_domain, target_url, anchor_text, anchor_type,
                link_type, is_dofollow, is_lost, first_seen, last_seen,
                source_dr, source_traffic, source_keywords_count,
                toxicity_score, toxicity_level, confidence, session_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (e.get("id", uuid4().hex[:12]), e["source_url"], e.get("source_domain", ""),
             e["target_url"], e.get("anchor_text", ""), e.get("anchor_type", "generic"),
             e.get("link_type", "editorial"), 1 if e.get("is_dofollow", True) else 0,
             1 if e.get("is_lost") else 0,
             e.get("first_seen"), e.get("last_seen"),
             e.get("source_dr", 0), e.get("source_traffic", 0),
             e.get("source_keywords_count", 0), e.get("toxicity_score", 0),
             e.get("toxicity_level", "safe"), e.get("confidence", "medium"),
             e.get("session_id", "")))
        count += 1
    conn.commit()
    conn.close()
    return count


def get_backlinks(domain: str = "", limit: int = 500) -> list[dict]:
    conn = _get_conn()
    if domain:
        rows = conn.execute(
            "SELECT * FROM backlinks WHERE source_domain = ? OR target_url LIKE ? ORDER BY source_dr DESC LIMIT ?",
            (domain, f"%{domain}%", limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM backlinks ORDER BY source_dr DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Referring Domains ─────────────────────────────────────────────────

def insert_domains_batch(entries: list[dict]) -> int:
    conn = _get_conn()
    count = 0
    for e in entries:
        conn.execute(
            """INSERT OR REPLACE INTO referring_domains
               (id, domain, domain_rating, topical_score, link_scarcity, geo_relevance,
                backlinks_count, first_seen, last_seen, domain_type, country, language,
                is_competitor, trust_flow, citation_flow, session_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (e.get("id", uuid4().hex[:12]), e["domain"],
             e.get("domain_rating", 0), e.get("topical_score", 0),
             e.get("link_scarcity", 0), e.get("geo_relevance", 0),
             e.get("backlinks_count", 0), e.get("first_seen"), e.get("last_seen"),
             e.get("domain_type", "blog"), e.get("country", ""),
             e.get("language", "fr"), 1 if e.get("is_competitor") else 0,
             e.get("trust_flow", 0), e.get("citation_flow", 0),
             e.get("session_id", "")))
        count += 1
    conn.commit()
    conn.close()
    return count


def get_domains(limit: int = 200) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM referring_domains ORDER BY domain_rating DESC LIMIT ?",
        (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Opportunities ─────────────────────────────────────────────────────

def insert_opportunities_batch(entries: list[dict]) -> int:
    conn = _get_conn()
    count = 0
    for e in entries:
        conn.execute(
            """INSERT OR REPLACE INTO backlink_opportunities
               (id, domain, url, contact_email, contact_name, domain_rating, topical_score,
                opportunity_type, priority, impact_score, feasibility_score, cost_estime,
                effort_estime, roi_estime, status, source, description, keywords_cibles, session_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (e.get("id", uuid4().hex[:12]), e["domain"], e.get("url", ""),
             e.get("contact_email", ""), e.get("contact_name", ""),
             e.get("domain_rating", 0), e.get("topical_score", 0),
             e.get("opportunity_type", "guest_post"), e.get("priority", "P2"),
             e.get("impact_score", 0), e.get("feasibility_score", 0),
             e.get("cost_estime", 0), e.get("effort_estime", "2h"),
             e.get("roi_estime", 0), e.get("status", "prospect"),
             e.get("source", ""), e.get("description", ""),
             json.dumps(e.get("keywords_cibles", [])), e.get("session_id", "")))
        count += 1
    conn.commit()
    conn.close()
    return count


def get_opportunities(status: str = "", priority: str = "", limit: int = 200) -> list[dict]:
    conn = _get_conn()
    query = "SELECT * FROM backlink_opportunities WHERE 1=1"
    params = []
    if status:
        query += " AND status = ?"
        params.append(status)
    if priority:
        query += " AND priority = ?"
        params.append(priority)
    query += " ORDER BY impact_score DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Campaigns CRM ─────────────────────────────────────────────────────

def insert_campaign(e: dict) -> str:
    cid = e.get("id", uuid4().hex[:12])
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO campaigns
           (id, opportunity_id, domain, contact_name, contact_email, contact_role,
            status, last_contact_date, next_followup_date, followup_count,
            notes, email_thread_id, cost_engaged, link_acquired, acquired_date,
            acquired_url, relationship_score, session_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cid, e.get("opportunity_id", ""), e["domain"],
         e.get("contact_name", ""), e.get("contact_email", ""), e.get("contact_role", ""),
         e.get("status", "prospect"), e.get("last_contact_date"), e.get("next_followup_date"),
         e.get("followup_count", 0), e.get("notes", ""), e.get("email_thread_id", ""),
         e.get("cost_engaged", 0), 1 if e.get("link_acquired") else 0,
         e.get("acquired_date"), e.get("acquired_url", ""),
         e.get("relationship_score", 0), e.get("session_id", "")))
    conn.commit()
    conn.close()
    return cid


def get_campaigns(status: str = "") -> list[dict]:
    conn = _get_conn()
    if status:
        rows = conn.execute(
            "SELECT * FROM campaigns WHERE status = ? ORDER BY next_followup_date",
            (status,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM campaigns ORDER BY next_followup_date").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_followups_today() -> list[dict]:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM campaigns WHERE next_followup_date <= ? AND status NOT IN ('publie','refuse','abandonne')",
        (today,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── DB Stats ──────────────────────────────────────────────────────────

def get_db_stats() -> dict:
    conn = _get_conn()
    tables = ["backlinks", "referring_domains", "toxic_domains",
              "backlink_opportunities", "campaigns", "campaign_results",
              "entity_mentions", "media_relationships", "portfolio_snapshots",
              "anchor_profiles"]
    stats = {}
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        stats[t] = count
    conn.close()
    return stats


# ─── Campaign Results (B08 — prepared from MVP) ────────────────────────

def insert_campaign_result(e: dict) -> str:
    rid = e.get("id", uuid4().hex[:12])
    conn = _get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO campaign_results
           (id, campaign_id, backlink_id, acquisition_date, cost, link_type,
            target_page, position_at_acquisition, traffic_at_acquisition,
            ranking_change_j30, ranking_change_j60, ranking_change_j90,
            traffic_change_j30, traffic_change_j60, traffic_change_j90,
            confidence_score, captured_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (rid, e.get("campaign_id", ""), e.get("backlink_id", ""),
         e.get("acquisition_date"), e.get("cost", 0), e.get("link_type", ""),
         e.get("target_page", ""), e.get("position_at_acquisition", 0),
         e.get("traffic_at_acquisition", 0), e.get("ranking_change_j30", 0),
         e.get("ranking_change_j60", 0), e.get("ranking_change_j90", 0),
         e.get("traffic_change_j30", 0), e.get("traffic_change_j60", 0),
         e.get("traffic_change_j90", 0), e.get("confidence_score", 0),
         datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return rid
