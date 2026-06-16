"""Configuration Loguru pour logs JSON structurés."""

import sys
from pathlib import Path

from loguru import logger

from hermes.config import LOG_DIRECTORY, LOG_LEVEL

LOG_FORMAT = (
    "{"
    '"timestamp": "{time:YYYY-MM-DDTHH:mm:ss.SSSZ}",'
    '"level": "{level}",'
    '"session_id": "{extra[session_id]}",'
    '"agent_id": "{extra[agent_id]}",'
    '"agent_name": "{extra[agent_name]}",'
    '"event": "{extra[event]}",'
    '"message": "{message}",'
    '"duration_ms": {extra[duration_ms]},'
    '"status": "{extra[status]}",'
    '"tokens_input": {extra[tokens_input]},'
    '"tokens_output": {extra[tokens_output]},'
    '"cost_estimated": {extra[cost_estimated]},'
    '"prompt_version": "{extra[prompt_version]}",'
    '"model_used": "{extra[model_used]}",'
    '"error": "{extra[error]}"'
    "}"
)


def configure_logging(session_id: str) -> None:
    """Configure les logs pour une session."""
    logger.remove()  # Retire le handler par défaut

    # Console : format lisible
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{extra[agent_id]}</cyan> | <level>{message}</level>",
        level=LOG_LEVEL,
        colorize=True,
    )

    # Fichier : JSON structuré
    log_path = LOG_DIRECTORY / f"hermes_{session_id}.jsonl"
    logger.add(
        str(log_path),
        format=LOG_FORMAT,
        level="DEBUG",
        serialize=False,  # On formate déjà en JSON-like
    )

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
