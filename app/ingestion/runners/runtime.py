"""Shared CLI/runtime helpers for scheduler-friendly ingestion runners."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from enum import Enum, IntEnum
import json
import logging
from typing import Any
from uuid import UUID

from app.config import settings
from app.ingestion.errors import IngestionConfigurationError
from app.models.enums import IngestionRunStatus
from app.services.errors import ServiceValidationError


class RunnerExitCode(IntEnum):
    """Process exit codes exposed by ingestion CLIs."""

    SUCCESS = 0
    FAILURE = 1
    PARTIAL = 2
    CONFIGURATION_ERROR = 3


class StructuredJsonFormatter(logging.Formatter):
    """Serialize log records as JSON objects for scheduler consumption."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        event = getattr(record, "event", None)
        if isinstance(event, str) and event:
            payload["event"] = event

        context = getattr(record, "context", None)
        if isinstance(context, Mapping) and context:
            payload["context"] = {
                str(key): _serialize_json_value(value)
                for key, value in context.items()
            }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, sort_keys=True, default=_serialize_json_value)


def configure_runner_logging(log_level: str | int) -> None:
    """Configure process logging for ingestion CLIs."""

    resolved_level = _resolve_log_level(log_level)
    handler = logging.StreamHandler()
    if settings.INGESTION_LOG_FORMAT == "json":
        handler.setFormatter(StructuredJsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(resolved_level)
    root_logger.addHandler(handler)


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    """Emit a structured runner log event with JSON-safe context."""

    logger.log(
        level,
        event,
        extra={
            "event": event,
            "context": {key: _serialize_json_value(value) for key, value in context.items()},
        },
    )


def exit_code_for_run_status(status: IngestionRunStatus) -> RunnerExitCode:
    """Return the CLI exit code for an ingestion run status."""

    if status == IngestionRunStatus.SUCCEEDED:
        return RunnerExitCode.SUCCESS
    if status == IngestionRunStatus.PARTIAL:
        return RunnerExitCode.PARTIAL
    return RunnerExitCode.FAILURE


def exit_code_for_summary(*, failed_sources: int, partial_sources: int) -> RunnerExitCode:
    """Return the CLI exit code for a unified ingestion summary."""

    if failed_sources > 0:
        return RunnerExitCode.FAILURE
    if partial_sources > 0:
        return RunnerExitCode.PARTIAL
    return RunnerExitCode.SUCCESS


def exit_code_for_exception(exc: Exception) -> RunnerExitCode:
    """Return the CLI exit code for an uncaught runner exception."""

    if isinstance(exc, (IngestionConfigurationError, ServiceValidationError)):
        return RunnerExitCode.CONFIGURATION_ERROR
    return RunnerExitCode.FAILURE


def _resolve_log_level(log_level: str | int) -> int:
    if isinstance(log_level, int):
        return log_level
    return getattr(logging, str(log_level).upper(), logging.INFO)


def _serialize_json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return _serialize_json_value(asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): _serialize_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_serialize_json_value(item) for item in value]
    return str(value)
