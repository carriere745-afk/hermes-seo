"""Gestionnaire de sessions Hermes SEO.

Sauvegarde, restauration, listing des sessions.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from hermes.core.exceptions import SessionNotFoundError
from hermes.models.session import AgentResult, SessionState


class SessionManager:
    """Gère la persistance des sessions sur disque."""

    def __init__(self, sessions_dir: Path):
        self._dir = Path(sessions_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._dir / f"{session_id}.json"

    def save(self, session: SessionState) -> Path:
        """Sauvegarde une session complète."""
        session.updated_at = datetime.now()
        path = self._path(session.session_id)
        path.write_text(
            session.model_dump_json(indent=2, exclude_none=False),
            encoding="utf-8",
        )
        return path

    def load(self, session_id: str) -> SessionState:
        """Charge une session depuis le disque."""
        path = self._path(session_id)
        if not path.exists():
            raise SessionNotFoundError(f"Session {session_id} introuvable dans {self._dir}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionState.model_validate(data)

    def load_or_none(self, session_id: str) -> Optional[SessionState]:
        """Charge une session, retourne None si absente."""
        try:
            return self.load(session_id)
        except SessionNotFoundError:
            return None

    def list_sessions(self) -> list[dict]:
        """Liste toutes les sessions sauvegardées."""
        sessions = []
        for f in sorted(self._dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            if "_backup" in f.name:
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                sessions.append({
                    "session_id": data.get("session_id", f.stem),
                    "keyword": data.get("keyword", ""),
                    "status": data.get("status", "unknown"),
                    "updated_at": data.get("updated_at", ""),
                    "agent_count": len(data.get("agent_results", {})),
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return sessions

    def delete(self, session_id: str) -> None:
        """Supprime une session."""
        path = self._path(session_id)
        if path.exists():
            path.unlink()

    def has_session(self, session_id: str) -> bool:
        return self._path(session_id).exists()

    def create_backup(self, session_id: str) -> Optional[Path]:
        """Crée une sauvegarde avant reprise."""
        path = self._path(session_id)
        if not path.exists():
            return None
        backup = self._dir / f"{session_id}_backup.json"
        backup.write_bytes(path.read_bytes())
        return backup

    def get_last_completed_agent(self, session: SessionState) -> Optional[str]:
        """Retourne l'ID du dernier agent complété."""
        completed = [
            agent_id
            for agent_id, result in session.agent_results.items()
            if result.status in ("completed", "skipped_auto", "skipped_user")
        ]
        return completed[-1] if completed else None

    def list_session_ids(self) -> list[str]:
        """Liste rapide des IDs de session (sans parsing JSON complet)."""
        return sorted(
            [
                f.stem
                for f in self._dir.glob("*.json")
                if "_backup" not in f.name
            ],
            key=lambda sid: (self._dir / f"{sid}.json").stat().st_mtime,
            reverse=True,
        )

    def count_sessions(self) -> int:
        """Nombre de fichiers session (hors backups)."""
        return sum(
            1
            for f in self._dir.glob("*.json")
            if "_backup" not in f.name
        )

    def get_session_metadata(self, session_id: str) -> Optional[dict]:
        """Lit uniquement les metadonnees d'une session (sans charger Pydantic)."""
        path = self._path(session_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            scores = data.get("scores") or {}
            cfg = data.get("config") or {}
            return {
                "session_id": data.get("session_id", session_id),
                "keyword": data.get("keyword", ""),
                "status": data.get("status", "unknown"),
                "mode": cfg.get("mode", "standard"),
                "secteur": cfg.get("secteur"),
                "created_at": data.get("created_at"),
                "updated_at": data.get("updated_at"),
                "total_cost": data.get("total_cost", 0) or 0,
                "total_tokens": data.get("total_tokens", 0) or 0,
                "score_total": scores.get("score_total"),
                "agent_count": len(data.get("agent_results", {})),
                "error_count": data.get("error_count", 0) or 0,
                "dry_run": cfg.get("dry_run", True),
            }
        except (json.JSONDecodeError, Exception):
            return None
