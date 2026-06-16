"""Tests du service d'archivage.

Utilise les fixtures de test dans tests/fixtures/sessions/ et tests/fixtures/logs/.
"""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from hermes.core.archive_service import ArchiveService
from hermes.models.archive import (
    BudgetSnapshot,
    ExportFormat,
    MetaArchiveEntry,
    RetentionPolicy,
    SessionFilter,
    TimelineEntry,
)
from hermes.models.common import QualityMode, SessionStatus


FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def archive_service():
    """ArchiveService isole avec donnees temporaires."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        sessions_dir = tmp_path / "sessions"
        logs_dir = tmp_path / "logs"
        archive_dir = tmp_path / "archive"
        sessions_dir.mkdir()
        logs_dir.mkdir()

        yield ArchiveService(
            sessions_dir=sessions_dir,
            logs_dir=logs_dir,
            archive_dir=archive_dir,
        )


@pytest.fixture
def populated_service(archive_service):
    """ArchiveService avec fixtures chargees."""
    # Copier les fixtures sessions
    for fixture_file in (FIXTURES / "sessions").glob("*.json"):
        dest = archive_service._sessions_dir / fixture_file.name
        dest.write_text(fixture_file.read_text(encoding="utf-8"), encoding="utf-8")

    # Copier les fixtures logs
    for log_file in (FIXTURES / "logs").glob("*.jsonl"):
        dest = archive_service._logs_dir / log_file.name
        dest.write_text(log_file.read_text(encoding="utf-8"), encoding="utf-8")

    archive_service._rebuild_index()
    return archive_service


# ─── Liste et filtres ──────────────────────────────────────────────

class TestListSessions:
    def test_empty(self, archive_service):
        page = archive_service.list_sessions()
        assert page.total == 0
        assert page.items == []

    def test_populated(self, populated_service):
        page = populated_service.list_sessions()
        assert page.total == 3

    def test_filter_search(self, populated_service):
        f = SessionFilter(search="logiciel")
        page = populated_service.list_sessions(f)
        assert page.total == 1
        assert page.items[0].keyword == "logiciel seo entreprise"

    def test_filter_search_case_insensitive(self, populated_service):
        f = SessionFilter(search="ASSURANCE")
        page = populated_service.list_sessions(f)
        assert page.total == 1

    def test_filter_status(self, populated_service):
        f = SessionFilter(status=[SessionStatus.COMPLETED])
        page = populated_service.list_sessions(f)
        assert page.total == 1

    def test_filter_status_failed(self, populated_service):
        f = SessionFilter(status=[SessionStatus.FAILED])
        page = populated_service.list_sessions(f)
        assert page.total == 1

    def test_filter_mode(self, populated_service):
        f = SessionFilter(mode=[QualityMode.PREMIUM])
        page = populated_service.list_sessions(f)
        assert page.total == 1
        assert page.items[0].mode == "premium"

    def test_filter_mode_fast(self, populated_service):
        f = SessionFilter(mode=[QualityMode.FAST])
        page = populated_service.list_sessions(f)
        assert page.total == 1
        assert page.items[0].keyword == "test minimal"

    def test_filter_only_failed(self, populated_service):
        f = SessionFilter(only_failed=True)
        page = populated_service.list_sessions(f)
        assert page.total == 1
        assert page.items[0].status == "failed"

    def test_filter_min_score(self, populated_service):
        f = SessionFilter(min_score=80)
        page = populated_service.list_sessions(f)
        assert page.total == 1
        assert page.items[0].score_total == 82

    def test_filter_min_score_none(self, populated_service):
        f = SessionFilter(min_score=90)
        page = populated_service.list_sessions(f)
        assert page.total == 0

    def test_filter_date_from(self, populated_service):
        f = SessionFilter(date_from=datetime(2026, 6, 15))
        page = populated_service.list_sessions(f)
        assert page.total >= 1

    def test_filter_date_to(self, populated_service):
        f = SessionFilter(date_to=datetime(2026, 6, 16))
        page = populated_service.list_sessions(f)
        assert page.total >= 1

    def test_pagination(self, populated_service):
        f = SessionFilter(page=1, page_size=1)
        page = populated_service.list_sessions(f)
        assert len(page.items) <= 1
        assert page.total == 3
        assert page.total_pages >= 3

    def test_pagination_page_2(self, populated_service):
        f = SessionFilter(page=2, page_size=1)
        page = populated_service.list_sessions(f)
        assert page.page == 2

    def test_filter_dry_run_true(self, populated_service):
        f = SessionFilter(dry_run=True)
        page = populated_service.list_sessions(f)
        assert page.total == 2

    def test_filter_dry_run_false(self, populated_service):
        f = SessionFilter(dry_run=False)
        page = populated_service.list_sessions(f)
        assert page.total == 1


# ─── Detail ───────────────────────────────────────────────────────

class TestGetSessionDetail:
    def test_completed(self, populated_service):
        detail = populated_service.get_session_detail("test001cmp")
        assert detail.session_id == "test001cmp"
        assert detail.keyword == "logiciel seo entreprise"
        assert detail.status == "completed"
        assert detail.total_cost == 0.265
        assert detail.total_tokens == 22600
        assert detail.has_content is True
        assert detail.content_preview is not None
        assert len(detail.agents) == 9
        assert detail.scores is not None
        assert detail.scores["score_total"] == 82

    def test_failed(self, populated_service):
        detail = populated_service.get_session_detail("test002err")
        assert detail.session_id == "test002err"
        assert detail.status == "failed"
        assert detail.error_count == 1

    def test_minimal(self, populated_service):
        detail = populated_service.get_session_detail("test003min")
        assert detail.session_id == "test003min"
        assert detail.status == "created"
        assert detail.agents == []

    def test_not_found(self, populated_service):
        with pytest.raises(Exception):
            populated_service.get_session_detail("nonexistent")

    def test_logs_included(self, populated_service):
        detail = populated_service.get_session_detail("test001cmp")
        assert len(detail.log_events) == 7
        assert detail.log_events[0].event == "agent_started"

    def test_budget_summary(self, populated_service):
        detail = populated_service.get_session_detail("test001cmp")
        assert detail.budget_summary is not None
        assert detail.budget_summary["tokens_used"] == 22600
        assert detail.budget_summary["cost_used"] == 0.265


# ─── Statistiques ────────────────────────────────────────────────

class TestGetStats:
    def test_empty(self, archive_service):
        stats = archive_service.get_stats()
        assert stats.total_sessions == 0
        assert stats.average_score is None

    def test_populated(self, populated_service):
        stats = populated_service.get_stats()
        assert stats.total_sessions == 3
        assert stats.total_completed == 1
        assert stats.total_failed == 1
        assert stats.total_tokens > 0
        assert stats.total_cost > 0
        assert stats.average_score is not None
        assert stats.sessions_by_status["completed"] == 1
        assert stats.sessions_by_status["failed"] == 1
        assert stats.sessions_by_mode["premium"] == 1
        assert stats.sessions_by_mode["standard"] == 1
        assert stats.sessions_by_mode["fast"] == 1
        assert len(stats.sessions_per_day) >= 2
        assert stats.top_keywords is not None
        assert stats.period_start is not None
        assert stats.period_end is not None


# ─── Export ───────────────────────────────────────────────────────

class TestExportSession:
    def test_export_json(self, populated_service):
        data = populated_service.export_session("test001cmp", ExportFormat.JSON)
        parsed = json.loads(data)
        assert parsed["session_id"] == "test001cmp"

    def test_export_csv(self, populated_service):
        data = populated_service.export_session("test001cmp", ExportFormat.CSV)
        assert "agent_id" in data
        assert "agent_00" in data or "agent_01" in data

    def test_export_markdown(self, populated_service):
        data = populated_service.export_session("test001cmp", ExportFormat.MARKDOWN)
        assert "logiciel seo entreprise" in data
        assert "test001cmp" in data

    def test_export_not_found(self, populated_service):
        with pytest.raises(Exception):
            populated_service.export_session("nonexistent", ExportFormat.JSON)

    def test_export_filtered_json(self, populated_service):
        f = SessionFilter(status=[SessionStatus.COMPLETED])
        data = populated_service.export_filtered(f, ExportFormat.JSON)
        parsed = json.loads(data)
        assert len(parsed) == 1
        assert parsed[0]["session_id"] == "test001cmp"

    def test_export_filtered_csv(self, populated_service):
        f = SessionFilter()
        data = populated_service.export_filtered(f, ExportFormat.CSV)
        assert "session_id" in data


# ─── Delete ───────────────────────────────────────────────────────

class TestDeleteSession:
    def test_delete_existing(self, populated_service):
        assert populated_service.delete_session("test003min") is True
        page = populated_service.list_sessions()
        assert page.total == 2

    def test_delete_with_logs(self, populated_service):
        populated_service.delete_session("test001cmp")
        page = populated_service.list_sessions()
        assert page.total == 2

    def test_delete_nonexistent(self, populated_service):
        assert populated_service.delete_session("nonexistent") is False

    def test_bulk_delete(self, populated_service):
        results = populated_service.bulk_delete(["test001cmp", "test002err", "nonexistent"])
        assert results["test001cmp"] is True
        assert results["test002err"] is True
        assert results["nonexistent"] is False
        page = populated_service.list_sessions()
        assert page.total == 1
        assert page.items[0].session_id == "test003min"


# ─── Archive / Unarchive ────────────────────────────────────────────

class TestArchiveUnarchive:
    def test_archive(self, populated_service):
        assert populated_service.archive_session("test001cmp") is True
        # Ne devrait plus etre dans la liste active
        page = populated_service.list_sessions()
        assert page.total == 2
        # Devrait etre dans les archives
        f = SessionFilter(include_archived=True)
        page_all = populated_service.list_sessions(f)
        assert page_all.total == 3

    def test_unarchive(self, populated_service):
        populated_service.archive_session("test001cmp")
        assert populated_service.unarchive_session("test001cmp") is True
        page = populated_service.list_sessions()
        assert page.total == 3

    def test_archive_nonexistent(self, populated_service):
        assert populated_service.archive_session("nonexistent") is False

    def test_unarchive_nonexistent(self, populated_service):
        assert populated_service.unarchive_session("nonexistent") is False

    def test_detail_after_archive(self, populated_service):
        """Le detail doit rester accessible apres archivage."""
        populated_service.archive_session("test001cmp")
        detail = populated_service.get_session_detail("test001cmp")
        assert detail.session_id == "test001cmp"
        assert detail.keyword == "logiciel seo entreprise"


# ─── Retention ──────────────────────────────────────────────────────

class TestRetentionPolicy:
    def test_dry_run(self, populated_service):
        policy = RetentionPolicy(archive_after_days=0)  # Tout archiver
        result = populated_service.run_retention_policy(policy, dry_run=True)
        assert len(result["to_archive"]) >= 0
        # Rien ne doit etre effectivement archive
        page = populated_service.list_sessions()
        assert page.total == 3

    def test_execute(self, populated_service):
        policy = RetentionPolicy(archive_after_days=0, delete_after_days=0)
        result = populated_service.run_retention_policy(policy, dry_run=False)
        assert "archived" in result
        assert "deleted" in result


# ─── Timeline ────────────────────────────────────────────────────────

class TestTimeline:
    def test_record_and_get(self, populated_service):
        entry = TimelineEntry(
            event_type="session_created",
            session_id="new123",
            keyword="nouveau test",
            description="Test timeline event",
        )
        populated_service.record_timeline_event(entry)

        events = populated_service.get_timeline(limit=10)
        assert len(events) >= 1
        assert events[0].session_id == "new123"

    def test_filter_by_type(self, populated_service):
        populated_service.record_timeline_event(
            TimelineEntry(event_type="milestone", description="Milestone test")
        )
        events = populated_service.get_timeline(
            limit=10, event_type="milestone"
        )
        assert len(events) == 1
        assert events[0].event_type == "milestone"

    def test_empty_timeline(self, archive_service):
        events = archive_service.get_timeline()
        assert events == []


# ─── Meta-archivage ──────────────────────────────────────────────────

class TestMetaArchive:
    def test_record_and_get(self, populated_service):
        entry = MetaArchiveEntry(
            event_type="deployment",
            title="Deploy v1.0",
            description="Premier deploiement Streamlit Cloud",
            version="v1.0.0",
        )
        populated_service.record_meta_event(entry)

        events = populated_service.get_meta_events(limit=10)
        assert len(events) == 1
        assert events[0].title == "Deploy v1.0"
        assert events[0].version == "v1.0.0"

    def test_filter_by_type(self, populated_service):
        populated_service.record_meta_event(
            MetaArchiveEntry(
                event_type="milestone",
                title="Jalon",
                description="Un jalon",
            )
        )
        events = populated_service.get_meta_events(
            limit=10, event_type="milestone"
        )
        assert len(events) == 1

    def test_empty(self, archive_service):
        events = archive_service.get_meta_events()
        assert events == []


# ─── Budget ──────────────────────────────────────────────────────────

class TestBudgetHistory:
    def test_record(self, populated_service):
        snap = BudgetSnapshot(
            session_id="test_budget",
            keyword="budget test",
            total_tokens=5000,
            total_cost=0.05,
        )
        populated_service.record_budget_snapshot(snap)
        history = populated_service.get_budget_history()
        assert len(history) >= 1

    def test_empty(self, archive_service):
        history = archive_service.get_budget_history()
        assert history == []


# ─── Index ───────────────────────────────────────────────────────────

class TestIndex:
    def test_rebuild(self, populated_service):
        entries = populated_service._rebuild_index()
        assert len(entries) == 3

    def test_needs_rebuild_after_new_file(self, populated_service):
        populated_service._rebuild_index()
        assert populated_service._index_needs_rebuild() is False

        new_session = {
            "session_id": "new_session",
            "keyword": "nouveau mot cle",
            "status": "created",
            "config": {"mode": "standard", "dry_run": True},
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "agent_results": {},
            "total_tokens": 0,
            "total_cost": 0.0,
            "error_count": 0,
        }
        import time
        time.sleep(0.1)
        (populated_service._sessions_dir / "new_session.json").write_text(
            json.dumps(new_session), encoding="utf-8"
        )
        assert populated_service._index_needs_rebuild() is True

    def test_metadata_extraction(self, populated_service):
        entries = populated_service._get_index()
        assert len(entries) == 3
        for entry in entries:
            assert "session_id" in entry
            assert "keyword" in entry
            assert "status" in entry
            assert "mode" in entry


# ─── SessionManager extensions ───────────────────────────────────────

class TestSessionManagerExtensions:
    def test_list_session_ids(self, populated_service):
        ids = populated_service._session_manager.list_session_ids()
        assert len(ids) == 3
        assert "test001cmp" in ids

    def test_count_sessions(self, populated_service):
        count = populated_service._session_manager.count_sessions()
        assert count == 3

    def test_get_metadata(self, populated_service):
        meta = populated_service._session_manager.get_session_metadata("test001cmp")
        assert meta is not None
        assert meta["keyword"] == "logiciel seo entreprise"
        assert meta["status"] == "completed"
        assert meta["total_cost"] == 0.265

    def test_get_metadata_not_found(self, populated_service):
        meta = populated_service._session_manager.get_session_metadata("nonexistent")
        assert meta is None
