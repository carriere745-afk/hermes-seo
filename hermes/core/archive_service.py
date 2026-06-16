"""Service d'archivage global pour Hermes SEO.

Agrege les donnees de sessions, logs et ChromaDB pour offrir
historique, recherche, statistiques, export et retention.
"""

import csv
import gzip
import io
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from hermes.config import LOG_DIRECTORY, SESSION_DIRECTORY
from hermes.core.exceptions import SessionNotFoundError
from hermes.core.session_manager import SessionManager
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


class ArchiveService:
    """Agrege et sert les donnees d'archivage depuis toutes les couches de persistance.

    Wrappe SessionManager pour le CRUD session et ajoute :
    - Parsing des logs JSONL
    - Agregation cross-session (statistiques)
    - Historique budget
    - Timeline projet
    - Meta-archivage (deploiements, jalons)
    - Export multi-format
    - Retention (auto-archive, nettoyage)
    """

    def __init__(
        self,
        sessions_dir: Optional[Path] = None,
        logs_dir: Optional[Path] = None,
        archive_dir: Optional[Path] = None,
    ):
        self._sessions_dir = Path(sessions_dir or SESSION_DIRECTORY)
        self._logs_dir = Path(logs_dir or LOG_DIRECTORY)
        self._archive_dir = Path(
            archive_dir or (self._sessions_dir.parent / "archive")
        )
        self._archive_sessions_dir = self._archive_dir / "sessions"
        self._timeline_path = self._archive_dir / "timeline.jsonl"
        self._meta_path = self._archive_dir / "meta.jsonl"
        self._budget_history_path = self._archive_dir / "budget_history.jsonl"
        self._index_path = self._archive_dir / "index.json"

        for d in [self._archive_dir, self._archive_sessions_dir]:
            d.mkdir(parents=True, exist_ok=True)
        for p in [self._timeline_path, self._meta_path, self._budget_history_path]:
            if not p.exists():
                p.write_text("", encoding="utf-8")

        self._session_manager = SessionManager(self._sessions_dir)

    # ─── Index (cache ultra-leger pour listings rapides) ─────────────

    def _rebuild_index(self) -> list[dict]:
        """Reconstruit l'index leger de toutes les sessions."""
        entries = []
        for f in sorted(
            self._sessions_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            if "_backup" in f.name:
                continue
            try:
                entry = self._extract_metadata(f)
                if entry:
                    entries.append(entry)
            except Exception:
                continue

        archived_entries = self._read_archived_index()
        entries.extend(archived_entries)

        self._index_path.write_text(
            json.dumps(entries, indent=2, default=str), encoding="utf-8"
        )
        return entries

    def _get_index(self) -> list[dict]:
        """Retourne l'index, le reconstruit si necessaire."""
        if self._index_needs_rebuild():
            return self._rebuild_index()
        try:
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return self._rebuild_index()

    def _index_needs_rebuild(self) -> bool:
        """Verifie si l'index doit etre reconstruit."""
        if not self._index_path.exists():
            return True
        index_mtime = self._index_path.stat().st_mtime
        for f in self._sessions_dir.glob("*.json"):
            if "_backup" in f.name:
                continue
            if f.stat().st_mtime > index_mtime:
                return True
        return False

    def _extract_metadata(self, path: Path) -> Optional[dict]:
        """Extrait les metadonnees legeres d'un fichier session JSON."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            scores = data.get("scores") or {}
            cfg = data.get("config") or {}
            created = data.get("created_at")
            updated = data.get("updated_at")
            duration = None
            if created and updated:
                try:
                    c = datetime.fromisoformat(created)
                    u = datetime.fromisoformat(updated)
                    duration = int((u - c).total_seconds())
                except (ValueError, TypeError):
                    pass
            return {
                "session_id": data.get("session_id", path.stem),
                "keyword": data.get("keyword", ""),
                "status": data.get("status", "unknown"),
                "mode": cfg.get("mode", "standard"),
                "secteur": cfg.get("secteur"),
                "created_at": created,
                "updated_at": updated,
                "total_cost": data.get("total_cost", 0) or 0,
                "total_tokens": data.get("total_tokens", 0) or 0,
                "score_total": scores.get("score_total"),
                "score_threshold_met": scores.get("seuil_atteint"),
                "agent_count": len(data.get("agent_results", {})),
                "error_count": data.get("error_count", 0) or 0,
                "dry_run": cfg.get("dry_run", True),
                "duration_seconds": duration,
                "is_archived": False,
                "has_logs": self._has_logs(data.get("session_id", "")),
                "replay_count": 0,
            }
        except (json.JSONDecodeError, Exception):
            return None

    def _read_archived_index(self) -> list[dict]:
        """Lit les sessions archivees depuis le dossier archive/sessions/."""
        entries = []
        if not self._archive_sessions_dir.exists():
            return entries
        for f in sorted(
            self._archive_sessions_dir.glob("*.gz"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(gzip.decompress(f.read_bytes()))
                scores = data.get("scores") or {}
                cfg = data.get("config") or {}
                created = data.get("created_at")
                updated = data.get("updated_at")
                duration = None
                if created and updated:
                    try:
                        duration = int(
                            (
                                datetime.fromisoformat(updated)
                                - datetime.fromisoformat(created)
                            ).total_seconds()
                        )
                    except (ValueError, TypeError):
                        pass
                entries.append(
                    {
                        "session_id": data.get("session_id", f.stem.replace(".json", "")),
                        "keyword": data.get("keyword", ""),
                        "status": data.get("status", "unknown"),
                        "mode": cfg.get("mode", "standard"),
                        "secteur": cfg.get("secteur"),
                        "created_at": created,
                        "updated_at": updated,
                        "total_cost": data.get("total_cost", 0) or 0,
                        "total_tokens": data.get("total_tokens", 0) or 0,
                        "score_total": scores.get("score_total"),
                        "score_threshold_met": scores.get("seuil_atteint"),
                        "agent_count": len(data.get("agent_results", {})),
                        "error_count": data.get("error_count", 0) or 0,
                        "dry_run": cfg.get("dry_run", True),
                        "duration_seconds": duration,
                        "is_archived": True,
                        "has_logs": False,
                        "replay_count": 0,
                    }
                )
            except Exception:
                continue
        return entries

    def _has_logs(self, session_id: str) -> bool:
        return (self._logs_dir / f"hermes_{session_id}.jsonl").exists()

    # ─── Listing, filtrage, pagination ──────────────────────────────

    def list_sessions(self, filter_obj: Optional[SessionFilter] = None) -> ArchivePage:
        """Liste les sessions avec filtres, recherche et pagination."""
        f = filter_obj or SessionFilter()
        entries = self._get_index()

        # Appliquer les filtres
        entries = self._apply_filters(entries, f)

        # Pagination
        total = len(entries)
        total_pages = max(1, (total + f.page_size - 1) // f.page_size)
        page = min(f.page, total_pages) if total_pages > 0 else 1
        start = (page - 1) * f.page_size
        end = start + f.page_size

        items = [
            ArchiveEntry(**e) for e in entries[start:end]
        ]
        return ArchivePage(
            items=items,
            total=total,
            page=page,
            page_size=f.page_size,
            total_pages=total_pages,
        )

    def _apply_filters(
        self, entries: list[dict], f: SessionFilter
    ) -> list[dict]:
        """Applique tous les filtres a la liste d'entrees."""
        if f.include_archived is False:
            entries = [e for e in entries if not e.get("is_archived", False)]

        if f.search:
            q = f.search.lower()
            entries = [
                e
                for e in entries
                if q in e.get("keyword", "").lower()
                or q in e.get("session_id", "").lower()
            ]

        if f.status:
            status_vals = {s.value if hasattr(s, "value") else s for s in f.status}
            entries = [e for e in entries if e.get("status") in status_vals]

        if f.mode:
            mode_vals = {m.value if hasattr(m, "value") else m for m in f.mode}
            entries = [e for e in entries if e.get("mode") in mode_vals]

        if f.secteur:
            entries = [
                e for e in entries if e.get("secteur") in set(f.secteur)
            ]

        if f.date_from:
            entries = [
                e
                for e in entries
                if e.get("created_at")
                and datetime.fromisoformat(str(e["created_at"])) >= f.date_from
            ]

        if f.date_to:
            entries = [
                e
                for e in entries
                if e.get("created_at")
                and datetime.fromisoformat(str(e["created_at"])) <= f.date_to
            ]

        if f.only_with_scores:
            entries = [e for e in entries if e.get("score_total") is not None]

        if f.only_failed:
            entries = [e for e in entries if e.get("status") == "failed"]

        if f.dry_run is not None:
            entries = [e for e in entries if e.get("dry_run") == f.dry_run]

        if f.min_score is not None:
            entries = [
                e
                for e in entries
                if e.get("score_total") is not None
                and e["score_total"] >= f.min_score
            ]

        if f.max_score is not None:
            entries = [
                e
                for e in entries
                if e.get("score_total") is not None
                and e["score_total"] <= f.max_score
            ]

        # Tri
        sort_key = f.sort_by if f.sort_by in ArchiveEntry.model_fields else "updated_at"
        reverse = f.sort_order == "desc"
        entries.sort(
            key=lambda e: e.get(sort_key) or "",
            reverse=reverse,
        )

        return entries

    # ─── Detail d'une session ───────────────────────────────────────

    def get_session_detail(self, session_id: str) -> SessionDetail:
        """Charge le detail complet d'une session (JSON + logs)."""
        try:
            session = self._session_manager.load(session_id)
        except SessionNotFoundError:
            # Chercher dans les archives
            archived = self._load_archived(session_id)
            if archived is None:
                raise
            session = archived

        cfg = session.config
        scores = session.scores or {}
        created = session.created_at
        updated = session.updated_at
        duration = None
        if created and updated:
            try:
                duration = int((updated - created).total_seconds())
            except (ValueError, TypeError):
                pass

        # Agents
        agents = []
        for aid, result in sorted(session.agent_results.items()):
            st = result.status.value if hasattr(result.status, "value") else str(result.status)
            agents.append(
                AgentDetail(
                    agent_id=aid,
                    agent_name=result.agent_name or aid,
                    status=st,
                    duration_ms=result.duration_ms,
                    tokens_input=result.tokens_input,
                    tokens_output=result.tokens_output,
                    cost_estimated=result.cost_estimated,
                    model_used=result.model_used,
                    prompt_version=result.prompt_version,
                    error_message=result.error_message,
                    skip_reason=result.skip_reason,
                    started_at=result.started_at,
                    finished_at=result.finished_at,
                )
            )

        # Logs
        log_events = self._read_logs(session_id)

        # Contenu
        has_content = bool(session.brouillon_html)
        content_preview = None
        if has_content and session.brouillon_html:
            content_preview = session.brouillon_html[:2000]

        # Budget
        budget_summary = {
            "tokens_used": session.total_tokens or 0,
            "cost_used": session.total_cost or 0,
            "token_budget": cfg.token_budget,
            "cost_budget": cfg.cost_budget,
            "cost_pct": (
                round((session.total_cost or 0) / cfg.cost_budget * 100, 1)
                if cfg.cost_budget > 0
                else 0
            ),
        }

        return SessionDetail(
            session_id=session.session_id,
            keyword=session.keyword or "",
            status=session.status.value if hasattr(session.status, "value") else str(session.status),
            config={
                "mode": cfg.mode.value if hasattr(cfg.mode, "value") else str(cfg.mode),
                "dry_run": cfg.dry_run,
                "secteur": cfg.secteur,
                "token_budget": cfg.token_budget,
                "cost_budget": cfg.cost_budget,
                "target_url": cfg.target_url,
                "target_cms": cfg.target_cms,
            },
            created_at=created,
            updated_at=updated,
            duration_seconds=duration,
            total_tokens=session.total_tokens or 0,
            total_cost=session.total_cost or 0,
            error_count=session.error_count or 0,
            scores=scores,
            agents=agents,
            log_events=log_events,
            has_content=has_content,
            content_preview=content_preview,
            budget_summary=budget_summary,
        )

    def _load_archived(self, session_id: str) -> Optional[Any]:
        """Charge une session depuis les archives compressees."""
        path = self._archive_sessions_dir / f"{session_id}.json.gz"
        if not path.exists():
            return None
        try:
            data = json.loads(gzip.decompress(path.read_bytes()))
            from hermes.models.session import SessionState

            return SessionState.model_validate(data)
        except Exception:
            return None

    def _read_logs(self, session_id: str) -> list[LogEvent]:
        """Lit les evenements JSONL pour une session donnee."""
        path = self._logs_dir / f"hermes_{session_id}.jsonl"
        if not path.exists():
            path = self._logs_dir / f"hermes_{session_id}.log"
        if not path.exists():
            return []
        events = []
        try:
            for line in path.read_text(encoding="utf-8").strip().splitlines():
                try:
                    obj = json.loads(line)
                    record = obj.get("record", obj)
                    events.append(
                        LogEvent(
                            timestamp=record.get("timestamp", ""),
                            level=record.get("level", ""),
                            agent_id=record.get("agent_id", ""),
                            agent_name=record.get("agent_name", ""),
                            event=record.get("event", ""),
                            duration_ms=record.get("duration_ms", 0),
                            status=record.get("status", ""),
                            tokens_input=record.get("tokens_input", 0),
                            tokens_output=record.get("tokens_output", 0),
                            cost_estimated=record.get("cost_estimated", 0.0),
                            prompt_version=record.get("prompt_version", ""),
                            model_used=record.get("model_used", ""),
                            error=record.get("error", ""),
                        )
                    )
                except json.JSONDecodeError:
                    continue
        except Exception:
            pass
        return events

    # ─── Statistiques agregees ──────────────────────────────────────

    def get_stats(self, include_archived: bool = False) -> ArchiveStats:
        """Calcule les statistiques agregees sur toutes les sessions."""
        entries = self._get_index()
        if not include_archived:
            entries = [e for e in entries if not e.get("is_archived", False)]

        if not entries:
            return ArchiveStats()

        total = len(entries)
        completed = sum(1 for e in entries if e.get("status") == "completed")
        failed = sum(1 for e in entries if e.get("status") == "failed")
        archived = sum(1 for e in entries if e.get("is_archived", False))
        total_tokens = sum(e.get("total_tokens", 0) or 0 for e in entries)
        total_cost = sum(e.get("total_cost", 0) or 0 for e in entries)
        with_scores = [e for e in entries if e.get("score_total") is not None]
        avg_score = (
            round(sum(e["score_total"] for e in with_scores) / len(with_scores), 1)
            if with_scores
            else None
        )
        avg_durations = [
            e["duration_seconds"]
            for e in entries
            if e.get("duration_seconds") is not None
        ]
        avg_dur = (
            round(sum(avg_durations) / len(avg_durations), 1)
            if avg_durations
            else None
        )

        # Par statut
        by_status: dict[str, int] = {}
        for e in entries:
            s = e.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1

        # Par mode
        by_mode: dict[str, int] = {}
        for e in entries:
            m = e.get("mode", "standard")
            by_mode[m] = by_mode.get(m, 0) + 1

        # Par secteur
        by_secteur: dict[str, int] = {}
        for e in entries:
            sec = e.get("secteur") or "autre"
            by_secteur[sec] = by_secteur.get(sec, 0) + 1

        # Par jour
        per_day: dict[str, int] = {}
        for e in entries:
            created = e.get("created_at")
            if created:
                day = str(created)[:10]
                per_day[day] = per_day.get(day, 0) + 1
        sessions_per_day = sorted(
            [{"date": d, "count": c} for d, c in per_day.items()],
            key=lambda x: x["date"],
        )

        # Top keywords (par score)
        with_kw = [
            e for e in entries if e.get("keyword") and e.get("score_total") is not None
        ]
        with_kw.sort(key=lambda e: e.get("score_total", 0) or 0, reverse=True)
        top_keywords = [
            {"keyword": e["keyword"], "score": e["score_total"]}
            for e in with_kw[:20]
        ]

        # Periode
        all_dates = [
            datetime.fromisoformat(str(e["created_at"]))
            for e in entries
            if e.get("created_at")
        ]
        period_start = min(all_dates) if all_dates else None
        period_end = max(all_dates) if all_dates else None

        # Budget total
        budget_used = sum(
            e.get("total_cost", 0) or 0 for e in entries if not e.get("dry_run")
        )

        return ArchiveStats(
            total_sessions=total,
            total_archived=archived,
            total_completed=completed,
            total_failed=failed,
            total_keywords=sum(1 for e in entries if e.get("keyword")),
            total_tokens=total_tokens,
            total_cost=round(total_cost, 4),
            sessions_with_scores=len(with_scores),
            average_score=avg_score,
            average_cost_per_session=round(total_cost / total, 4) if total else 0,
            average_tokens_per_session=round(total_tokens / total, 1) if total else 0,
            average_duration_seconds=avg_dur,
            sessions_by_status=by_status,
            sessions_by_mode=by_mode,
            sessions_by_secteur=by_secteur,
            sessions_per_day=sessions_per_day,
            top_keywords=top_keywords,
            budget_used_total=round(budget_used, 4),
            period_start=period_start,
            period_end=period_end,
        )

    # ─── Budget history ─────────────────────────────────────────────

    def get_budget_history(self, limit: int = 100) -> list[BudgetSnapshot]:
        """Retourne l'historique budget depuis le fichier dedie."""
        snapshots = []
        if self._budget_history_path.exists():
            try:
                for line in (
                    self._budget_history_path.read_text(encoding="utf-8")
                    .strip()
                    .splitlines()
                ):
                    try:
                        obj = json.loads(line)
                        snapshots.append(BudgetSnapshot(**obj))
                    except Exception:
                        continue
            except Exception:
                pass

        # Completer avec les sessions qui n'y sont pas encore
        existing_ids = {s.session_id for s in snapshots}
        entries = self._get_index()
        for e in entries:
            if e["session_id"] not in existing_ids and not e.get("is_archived"):
                cost = e.get("total_cost", 0) or 0
                tokens = e.get("total_tokens", 0) or 0
                if cost == 0 and tokens == 0:
                    continue
                snapshots.append(
                    BudgetSnapshot(
                        session_id=e["session_id"],
                        keyword=e.get("keyword", ""),
                        created_at=(
                            datetime.fromisoformat(str(e["created_at"]))
                            if e.get("created_at")
                            else None
                        ),
                        total_tokens=tokens,
                        total_cost=cost,
                        cost_percentage=0,
                        mode=e.get("mode", "standard"),
                        dry_run=e.get("dry_run", True),
                        agent_count=e.get("agent_count", 0),
                        score_total=e.get("score_total"),
                    )
                )

        snapshots.sort(
            key=lambda s: s.created_at or datetime.min,
            reverse=True,
        )
        return snapshots[:limit]

    def record_budget_snapshot(self, snapshot: BudgetSnapshot) -> None:
        """Enregistre un snapshot budget dans l'historique."""
        with open(self._budget_history_path, "a", encoding="utf-8") as fh:
            fh.write(snapshot.model_dump_json() + "\n")

    # ─── Timeline ───────────────────────────────────────────────────

    def get_timeline(
        self, limit: int = 100, event_type: Optional[str] = None
    ) -> list[TimelineEntry]:
        """Lit la timeline du projet."""
        entries = []
        if self._timeline_path.exists():
            try:
                lines = self._timeline_path.read_text(encoding="utf-8").strip().splitlines()
                for line in reversed(lines):
                    try:
                        obj = json.loads(line)
                        if event_type and obj.get("event_type") != event_type:
                            continue
                        entries.append(TimelineEntry(**obj))
                        if len(entries) >= limit:
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        return entries

    def record_timeline_event(self, entry: TimelineEntry) -> None:
        """Ajoute un evenement a la timeline."""
        with open(self._timeline_path, "a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")
        self._index_needs_rebuild.cache_clear() if hasattr(
            self._index_needs_rebuild, "cache_clear"
        ) else None

    # ─── Meta-archivage ─────────────────────────────────────────────

    def get_meta_events(
        self, limit: int = 50, event_type: Optional[str] = None
    ) -> list[MetaArchiveEntry]:
        """Lit les evenements meta (deploiements, jalons, changements config)."""
        entries = []
        if self._meta_path.exists():
            try:
                lines = self._meta_path.read_text(encoding="utf-8").strip().splitlines()
                for line in reversed(lines):
                    try:
                        obj = json.loads(line)
                        if event_type and obj.get("event_type") != event_type:
                            continue
                        entries.append(MetaArchiveEntry(**obj))
                        if len(entries) >= limit:
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        return entries

    def record_meta_event(self, entry: MetaArchiveEntry) -> None:
        """Enregistre un evenement meta."""
        with open(self._meta_path, "a", encoding="utf-8") as fh:
            fh.write(entry.model_dump_json() + "\n")

    # ─── Export ─────────────────────────────────────────────────────

    def export_session(
        self, session_id: str, fmt: ExportFormat = ExportFormat.JSON
    ) -> str:
        """Exporte une session dans le format demande."""
        detail = self.get_session_detail(session_id)

        if fmt == ExportFormat.JSON:
            return detail.model_dump_json(indent=2)

        if fmt == ExportFormat.CSV:
            output = io.StringIO()
            writer = csv.DictWriter(
                output,
                fieldnames=[
                    "agent_id", "agent_name", "status", "duration_ms",
                    "tokens_input", "tokens_output", "cost_estimated",
                    "model_used", "prompt_version",
                ],
            )
            writer.writeheader()
            for agent in detail.agents:
                writer.writerow({
                k: agent.model_dump().get(k)
                for k in [
                    "agent_id", "agent_name", "status", "duration_ms",
                    "tokens_input", "tokens_output", "cost_estimated",
                    "model_used", "prompt_version",
                ]
            })
            return output.getvalue()

        if fmt == ExportFormat.MARKDOWN:
            md = f"# Session: {detail.keyword}\n\n"
            md += f"**ID**: `{detail.session_id}`\n\n"
            md += f"**Status**: {detail.status} | **Mode**: {detail.config.get('mode', '?')}\n\n"
            md += f"**Cost**: ${detail.total_cost:.4f} | "
            md += f"**Tokens**: {detail.total_tokens}\n\n"
            if detail.scores:
                md += f"**Score**: {detail.scores.get('score_total', '?')}/100\n\n"
            md += "## Agents\n\n"
            md += "| Agent | Status | Duration | Tokens | Cost |\n"
            md += "|-------|--------|----------|--------|------|\n"
            for a in detail.agents:
                md += f"| {a.agent_name} | {a.status} | {a.duration_ms or '-'}ms "
                md += f"| {a.tokens_input or 0} | ${a.cost_estimated or 0:.4f} |\n"
            return md

        if fmt == ExportFormat.HTML:
            return self._export_html(detail)

        return detail.model_dump_json(indent=2)

    def export_filtered(
        self, filter_obj: SessionFilter, fmt: ExportFormat = ExportFormat.JSON
    ) -> str:
        """Exporte toutes les sessions correspondant aux filtres."""
        page = self.list_sessions(filter_obj)

        if fmt == ExportFormat.JSON:
            items = []
            for entry in page.items:
                try:
                    detail = self.get_session_detail(entry.session_id)
                    items.append(json.loads(detail.model_dump_json()))
                except Exception:
                    items.append(entry.model_dump())
            return json.dumps(items, indent=2)

        if fmt == ExportFormat.CSV:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                ["session_id", "keyword", "status", "mode", "cost", "tokens", "score"]
            )
            for entry in page.items:
                writer.writerow(
                    [
                        entry.session_id,
                        entry.keyword,
                        entry.status,
                        entry.mode,
                        entry.total_cost,
                        entry.total_tokens,
                        entry.score_total,
                    ]
                )
            return output.getvalue()

        return json.dumps([e.model_dump() for e in page.items], indent=2)

    def _export_html(self, detail: SessionDetail) -> str:
        """Genere un export HTML complet d'une session."""
        score = detail.scores.get("score_total", "?") if detail.scores else "?"
        return (
            f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<title>Hermes SEO — {detail.keyword}</title></head><body>"
            f"<h1>{detail.keyword}</h1>"
            f"<p>Session: {detail.session_id} | Score: {score}/100 | "
            f"Cost: ${detail.total_cost:.4f}</p>"
            f"</body></html>"
        )

    # ─── Delete ─────────────────────────────────────────────────────

    def delete_session(self, session_id: str) -> bool:
        """Supprime une session et ses logs associes."""
        deleted = False

        # Session JSON
        path = self._sessions_dir / f"{session_id}.json"
        if path.exists():
            path.unlink()
            deleted = True

        # Backup
        backup = self._sessions_dir / f"{session_id}_backup.json"
        if backup.exists():
            backup.unlink()

        # Archive compressee
        archived = self._archive_sessions_dir / f"{session_id}.json.gz"
        if archived.exists():
            archived.unlink()
            deleted = True

        # Logs
        for ext in (".jsonl", ".log"):
            log_path = self._logs_dir / f"hermes_{session_id}{ext}"
            if log_path.exists():
                log_path.unlink()

        if deleted:
            self._rebuild_index()
        return deleted

    def bulk_delete(self, session_ids: list[str]) -> dict[str, bool]:
        """Supprime plusieurs sessions. Retourne {id: succes}."""
        results = {}
        for sid in session_ids:
            results[sid] = self.delete_session(sid)
        return results

    # ─── Archive / Unarchive ────────────────────────────────────────

    def archive_session(self, session_id: str) -> bool:
        """Compresse une session et la deplace vers archive/sessions/."""
        src = self._sessions_dir / f"{session_id}.json"
        if not src.exists():
            return False

        try:
            data = src.read_bytes()
            compressed = gzip.compress(data)
            dest = self._archive_sessions_dir / f"{session_id}.json.gz"
            dest.write_bytes(compressed)
            src.unlink()

            # Supprimer aussi le backup
            backup = self._sessions_dir / f"{session_id}_backup.json"
            if backup.exists():
                backup.unlink()

            self._rebuild_index()
            self.record_timeline_event(
                TimelineEntry(
                    event_type="session_archived",
                    session_id=session_id,
                    description=f"Session {session_id} archivee (compressee)",
                )
            )
            return True
        except Exception:
            return False

    def unarchive_session(self, session_id: str) -> bool:
        """Restaure une session archivee vers le dossier sessions/."""
        src = self._archive_sessions_dir / f"{session_id}.json.gz"
        if not src.exists():
            return False

        try:
            data = gzip.decompress(src.read_bytes())
            dest = self._sessions_dir / f"{session_id}.json"
            dest.write_bytes(data)
            src.unlink()
            self._rebuild_index()
            self.record_timeline_event(
                TimelineEntry(
                    event_type="session_unarchived",
                    session_id=session_id,
                    description=f"Session {session_id} restauree depuis les archives",
                )
            )
            return True
        except Exception:
            return False

    # ─── Retention ──────────────────────────────────────────────────

    def run_retention_policy(
        self, policy: Optional[RetentionPolicy] = None, dry_run: bool = True
    ) -> dict:
        """Execute la politique de retention.

        Retourne un dict avec les listes 'to_archive', 'to_delete'
        (ou 'archived', 'deleted' si dry_run=False).
        """
        policy = policy or RetentionPolicy()
        entries = self._get_index()
        entries = [e for e in entries if not e.get("is_archived", False)]
        entries.sort(key=lambda e: str(e.get("updated_at") or ""), reverse=True)

        now = datetime.now()
        archive_cutoff = now - timedelta(days=policy.archive_after_days)
        delete_cutoff_archived = now - timedelta(days=policy.delete_after_days)

        to_archive = []
        to_delete = []

        # Identifier sessions a archiver (plus vieilles que archive_after_days)
        for e in entries:
            updated = e.get("updated_at")
            if updated:
                try:
                    dt = datetime.fromisoformat(str(updated))
                    if dt < archive_cutoff:
                        to_archive.append(e["session_id"])
                except (ValueError, TypeError):
                    pass

        # Identifier sessions a supprimer (dans archives, plus vieilles que delete_after_days)
        archived_entries = self._read_archived_index()
        for e in archived_entries:
            updated = e.get("updated_at")
            if updated:
                try:
                    dt = datetime.fromisoformat(str(updated))
                    if dt < delete_cutoff_archived:
                        to_delete.append(e["session_id"])
                except (ValueError, TypeError):
                    pass

        if dry_run:
            return {"to_archive": to_archive, "to_delete": to_delete}

        archived = []
        deleted = []
        for sid in to_archive:
            if self.archive_session(sid):
                archived.append(sid)
        for sid in to_delete:
            archived_path = self._archive_sessions_dir / f"{sid}.json.gz"
            if archived_path.exists():
                archived_path.unlink()
                deleted.append(sid)

        return {"archived": archived, "deleted": deleted}

    # ─── Enregistrement automatique depuis le pipeline ──────────────

    def record_session_created(self, session_id: str, keyword: str) -> None:
        """Enregistre la creation d'une session dans la timeline."""
        self.record_timeline_event(
            TimelineEntry(
                event_type="session_created",
                session_id=session_id,
                keyword=keyword,
                description=f"Session creee pour '{keyword}'",
            )
        )

    def record_session_completed(
        self, session_id: str, keyword: str, score: Optional[int] = None
    ) -> None:
        """Enregistre la completion d'une session."""
        desc = f"Session terminee pour '{keyword}'"
        if score is not None:
            desc += f" — Score: {score}/100"
        self.record_timeline_event(
            TimelineEntry(
                event_type="session_completed",
                session_id=session_id,
                keyword=keyword,
                description=desc,
                metadata={"score": score} if score is not None else None,
            )
        )
        self._rebuild_index()

    def record_session_failed(
        self, session_id: str, keyword: str, error: str
    ) -> None:
        """Enregistre l'echec d'une session."""
        self.record_timeline_event(
            TimelineEntry(
                event_type="session_failed",
                session_id=session_id,
                keyword=keyword,
                description=f"Session echouee pour '{keyword}' — {error}",
                metadata={"error": error},
            )
        )
        self._rebuild_index()
