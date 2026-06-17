"""Configuration Loguru pour logs JSON structurés."""

import json
import sys
from pathlib import Path

from loguru import logger

from hermes.config import LOG_DIRECTORY, LOG_LEVEL


def configure_logging(session_id: str) -> None:
    """Configure les logs pour une session."""
    logger.remove()

    # Console : format lisible
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{extra[agent_id]}</cyan> | <level>{message}</level>",
        level=LOG_LEVEL,
        colorize=True,
    )

    # Fichier JSONL : sink custom
    log_path = LOG_DIRECTORY / f"hermes_{session_id}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(str(log_path), "a", encoding="utf-8")

    def _write_jsonl(message):
        record = message.record
        fh.write(json.dumps({
            "timestamp": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record["level"].name,
            "session_id": record["extra"].get("session_id", ""),
            "agent_id": record["extra"].get("agent_id", ""),
            "agent_name": record["extra"].get("agent_name", ""),
            "event": record["extra"].get("event", ""),
            "message": record["message"],
            "duration_ms": record["extra"].get("duration_ms", 0),
            "status": record["extra"].get("status", ""),
            "tokens_input": record["extra"].get("tokens_input", 0),
            "tokens_output": record["extra"].get("tokens_output", 0),
            "cost_estimated": record["extra"].get("cost_estimated", 0.0),
            "prompt_version": record["extra"].get("prompt_version", ""),
            "model_used": record["extra"].get("model_used", ""),
            "error": record["extra"].get("error", ""),
        }, ensure_ascii=False) + "\n")
        fh.flush()

    logger.add(_write_jsonl, level="DEBUG")

    # Lier le session_id au logger
    logger.configure(extra={
        "session_id": session_id,
        "agent_id": "",
        "agent_name": "",
        "event": "",
        "duration_ms": 0,
        "status": "",
        "tokens_input": 0,
        "tokens_output": 0,
        "cost_estimated": 0.0,
        "prompt_version": "",
        "model_used": "",
        "error": "",
    })


def log_agent_start(agent_id: str, agent_name: str) -> None:
    logger.bind(
        agent_id=agent_id,
        agent_name=agent_name,
        event="agent_started",
    ).info(f"Démarrage {agent_name}")


def log_agent_completed(
    agent_id: str,
    agent_name: str,
    duration_ms: int,
    tokens_input: int = 0,
    tokens_output: int = 0,
    cost_estimated: float = 0.0,
    prompt_version: str = "",
    model_used: str = "",
) -> None:
    logger.bind(
        agent_id=agent_id,
        agent_name=agent_name,
        event="agent_completed",
        duration_ms=duration_ms,
        status="completed",
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost_estimated=cost_estimated,
        prompt_version=prompt_version,
        model_used=model_used,
    ).info(f"Terminé {agent_name} ({duration_ms}ms)")


def log_agent_failed(
    agent_id: str,
    agent_name: str,
    error: str,
    duration_ms: int = 0,
) -> None:
    logger.bind(
        agent_id=agent_id,
        agent_name=agent_name,
        event="agent_failed",
        duration_ms=duration_ms,
        status="failed",
        error=error,
    ).error(f"Échec {agent_name}: {error}")


def log_agent_skipped(
    agent_id: str,
    agent_name: str,
    skip_type: str,
    reason: str,
) -> None:
    logger.bind(
        agent_id=agent_id,
        agent_name=agent_name,
        event="agent_skipped",
        status=skip_type,
        error=reason,
    ).info(f"Ignoré {agent_name} ({skip_type}): {reason}")


def log_supervisor(verdict: object) -> None:
    from hermes.models.agent_data import SupervisorVerdict
    v = verdict if isinstance(verdict, SupervisorVerdict) else None
    logger.bind(
        agent_id="agent_00",
        agent_name="Superviseur",
        event="supervisor_check",
        status="blocked" if (v and not v.valid) else "valid",
        error="; ".join(v.blocked_reasons) if v and v.blocked_reasons else "",
    ).info(
        "Superviseur: " + ("BLOQUÉ" if v and not v.valid else "OK")
    )
