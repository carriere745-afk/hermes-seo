"""Tests des modeles d'archivage."""

import json
from datetime import datetime

import pytest

from hermes.models.archive import (
    AgentDetail,
    ArchiveEntry,
    ArchivePage,
    ArchiveStats,
    BudgetSnapshot,
    ExportFormat,
    LogEvent,
    MetaArchiveEntry,
    RetentionPolicy,
    SessionDetail,
    SessionFilter,
    TimelineEntry,
)
from hermes.models.common import QualityMode, SessionStatus


class TestExportFormat:
    def test_all_formats(self):
        assert ExportFormat.JSON.value == "json"
        assert ExportFormat.CSV.value == "csv"
        assert ExportFormat.MARKDOWN.value == "markdown"
        assert ExportFormat.HTML.value == "html"


class TestRetentionPolicy:
    def test_defaults(self):
        policy = RetentionPolicy()
        assert policy.archive_after_days == 30
        assert policy.delete_after_days == 365
        assert policy.keep_min_sessions == 10
        assert policy.compress_archives is True

    def test_custom(self):
        policy = RetentionPolicy(archive_after_days=7, delete_after_days=90)
        assert policy.archive_after_days == 7
        assert policy.delete_after_days == 90


class TestSessionFilter:
    def test_defaults(self):
        f = SessionFilter()
        assert f.page == 1
        assert f.page_size == 50
        assert f.sort_by == "updated_at"
        assert f.sort_order == "desc"
        assert f.include_archived is False

    def test_custom(self):
        f = SessionFilter(
            search="test",
            status=[SessionStatus.COMPLETED],
            mode=[QualityMode.PREMIUM],
            page=2,
            page_size=20,
            min_score=75,
        )
        assert f.search == "test"
        assert f.page == 2
        assert f.page_size == 20
        assert f.min_score == 75


class TestArchiveEntry:
    def test_minimal(self):
        entry = ArchiveEntry(
            session_id="abc123",
            keyword="test",
        )
        assert entry.session_id == "abc123"
        assert entry.keyword == "test"
        assert entry.status == "unknown"
        assert entry.total_cost == 0.0
        assert entry.agent_count == 0

    def test_full(self):
        entry = ArchiveEntry(
            session_id="xyz789",
            keyword="seo saas",
            status="completed",
            mode="premium",
            secteur="saas",
            total_cost=0.25,
            total_tokens=15000,
            score_total=82,
            agent_count=20,
        )
        assert entry.mode == "premium"
        assert entry.total_cost == 0.25
        assert entry.score_total == 82


class TestArchivePage:
    def test_pagination_first(self):
        page = ArchivePage(
            items=[],
            total=100,
            page=1,
            page_size=20,
            total_pages=5,
        )
        assert page.has_next is True
        assert page.has_prev is False

    def test_pagination_last(self):
        page = ArchivePage(
            items=[],
            total=100,
            page=5,
            page_size=20,
            total_pages=5,
        )
        assert page.has_next is False
        assert page.has_prev is True

    def test_pagination_middle(self):
        page = ArchivePage(
            items=[],
            total=100,
            page=3,
            page_size=20,
            total_pages=5,
        )
        assert page.has_next is True
        assert page.has_prev is True

    def test_pagination_single(self):
        page = ArchivePage(
            items=[],
            total=5,
            page=1,
            page_size=20,
            total_pages=1,
        )
        assert page.has_next is False
        assert page.has_prev is False


class TestAgentDetail:
    def test_minimal(self):
        agent = AgentDetail(agent_id="agent_01", agent_name="Brief")
        assert agent.status == "pending"
        assert agent.tokens_input is None


class TestLogEvent:
    def test_defaults(self):
        evt = LogEvent()
        assert evt.timestamp == ""


class TestSessionDetail:
    def test_minimal(self):
        detail = SessionDetail(session_id="abc", keyword="test")
        assert detail.session_id == "abc"
        assert detail.keyword == "test"
        assert detail.agents == []
        assert detail.log_events == []


class TestBudgetSnapshot:
    def test_defaults(self):
        snap = BudgetSnapshot(session_id="abc", keyword="test")
        assert snap.token_budget == 1_000_000
        assert snap.cost_budget == 5.0
        assert snap.total_tokens == 0
        assert snap.total_cost == 0.0


class TestTimelineEntry:
    def test_auto_fields(self):
        entry = TimelineEntry(
            event_type="session_created",
            description="Test event",
        )
        assert entry.event_id
        assert len(entry.event_id) == 20  # YYYYMMDDHHMMSSffffff
        assert entry.timestamp is not None
        assert entry.session_id is None

    def test_serialization(self):
        entry = TimelineEntry(
            event_type="session_completed",
            session_id="abc123",
            keyword="test",
            description="Session completed for test",
            metadata={"score": 82},
        )
        data = entry.model_dump_json()
        assert "session_completed" in data
        assert "abc123" in data


class TestMetaArchiveEntry:
    def test_required_fields(self):
        entry = MetaArchiveEntry(
            event_type="deployment",
            title="Deploy v0.2",
            description="Deploiement de la v0.2 sur Streamlit Cloud",
        )
        assert entry.event_type == "deployment"
        assert entry.title == "Deploy v0.2"
        assert entry.event_id

    def test_optional_version(self):
        entry = MetaArchiveEntry(
            event_type="milestone",
            title="Beta",
            description="Premiere beta",
            version="v0.1.0-beta",
        )
        assert entry.version == "v0.1.0-beta"


class TestArchiveStats:
    def test_empty(self):
        stats = ArchiveStats()
        assert stats.total_sessions == 0
        assert stats.average_score is None
        assert stats.total_cost == 0.0

    def test_with_data(self):
        stats = ArchiveStats(
            total_sessions=10,
            total_completed=8,
            total_failed=2,
            sessions_by_status={"completed": 8, "failed": 2},
            sessions_by_mode={"standard": 6, "premium": 4},
            average_score=78.5,
            total_cost=2.5,
            total_tokens=150000,
        )
        assert stats.total_sessions == 10
        assert stats.average_score == 78.5
        assert stats.total_cost == 2.5
        assert stats.sessions_by_status["completed"] == 8
