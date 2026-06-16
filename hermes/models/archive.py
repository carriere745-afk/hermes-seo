"""Modeles pour le systeme d'archivage global Hermes SEO.

Agrege les donnees de sessions, logs et ChromaDB pour offrir
historique, recherche, statistiques et export.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from hermes.models.common import QualityMode, SessionStatus


class ExportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"


class RetentionPolicy(BaseModel):
    archive_after_days: int = 30
    delete_after_days: int = 365
    keep_min_sessions: int = 10
    compress_archives: bool = True
    delete_empty_logs: bool = True
    run_on_startup: bool = False


class SessionFilter(BaseModel):
    search: Optional[str] = None
    status: Optional[list[SessionStatus]] = None
    mode: Optional[list[QualityMode]] = None
    secteur: Optional[list[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sort_by: str = "updated_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 50
    include_archived: bool = False
    only_with_scores: bool = False
    only_failed: bool = False
    dry_run: Optional[bool] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None


class ArchiveEntry(BaseModel):
    session_id: str
    keyword: str
    status: str = "unknown"
    mode: str = "standard"
    secteur: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    total_cost: float = 0.0
    total_tokens: int = 0
    score_total: Optional[int] = None
    score_threshold_met: Optional[bool] = None
    agent_count: int = 0
    error_count: int = 0
    dry_run: bool = True
    duration_seconds: Optional[int] = None
    is_archived: bool = False
    has_logs: bool = False
    replay_count: int = 0


class ArchivePage(BaseModel):
    items: list[ArchiveEntry]
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


class AgentDetail(BaseModel):
    agent_id: str
    agent_name: str = ""
    status: str = "pending"
    duration_ms: Optional[int] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_estimated: Optional[float] = None
    model_used: Optional[str] = None
    prompt_version: Optional[str] = None
    error_message: Optional[str] = None
    skip_reason: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class LogEvent(BaseModel):
    timestamp: str = ""
    level: str = ""
    agent_id: str = ""
    agent_name: str = ""
    event: str = ""
    duration_ms: int = 0
    status: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    cost_estimated: float = 0.0
    prompt_version: str = ""
    model_used: str = ""
    error: str = ""


class SessionDetail(BaseModel):
    session_id: str
    keyword: str
    status: str = "unknown"
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    error_count: int = 0
    scores: Optional[dict[str, Any]] = None
    agents: list[AgentDetail] = Field(default_factory=list)
    log_events: list[LogEvent] = Field(default_factory=list)
    has_content: bool = False
    content_preview: Optional[str] = None
    budget_summary: Optional[dict[str, Any]] = None


class BudgetSnapshot(BaseModel):
    session_id: str
    keyword: str
    created_at: Optional[datetime] = None
    total_tokens: int = 0
    total_cost: float = 0.0
    token_budget: int = 1_000_000
    cost_budget: float = 5.0
    cost_percentage: float = 0.0
    mode: str = "standard"
    dry_run: bool = True
    agent_count: int = 0
    score_total: Optional[int] = None


class TimelineEntry(BaseModel):
    event_id: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f")
    )
    event_type: str = ""
    session_id: Optional[str] = None
    keyword: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    description: str = ""
    metadata: Optional[dict[str, Any]] = None


class MetaArchiveEntry(BaseModel):
    event_id: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S%f")
    )
    event_type: str = ""
    title: str = ""
    description: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)
    version: Optional[str] = None
    actor: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class ArchiveStats(BaseModel):
    total_sessions: int = 0
    total_archived: int = 0
    total_completed: int = 0
    total_failed: int = 0
    total_keywords: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    sessions_with_scores: int = 0
    average_score: Optional[float] = None
    average_cost_per_session: float = 0.0
    average_tokens_per_session: float = 0.0
    average_duration_seconds: Optional[float] = None
    sessions_by_status: dict[str, int] = Field(default_factory=dict)
    sessions_by_mode: dict[str, int] = Field(default_factory=dict)
    sessions_by_secteur: dict[str, int] = Field(default_factory=dict)
    sessions_per_day: list[dict[str, Any]] = Field(default_factory=list)
    top_keywords: list[dict[str, Any]] = Field(default_factory=list)
    budget_used_total: float = 0.0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
