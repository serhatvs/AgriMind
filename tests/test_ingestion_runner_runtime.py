from __future__ import annotations

import json
import logging
from io import StringIO
from uuid import uuid4

from app.ingestion.runners.run_faostat import main as faostat_main
from app.ingestion.runners.run_nasa_power import main as nasa_power_main
from app.ingestion.runners.runtime import (
    RunnerExitCode,
    StructuredJsonFormatter,
    exit_code_for_run_status,
    exit_code_for_summary,
)
from app.ingestion.types import IngestionExecutionResult
from app.models.enums import IngestionRunStatus
from app.services.errors import ServiceValidationError


class _DummySession:
    def close(self) -> None:
        return None


def _build_result(status: IngestionRunStatus) -> IngestionExecutionResult:
    return IngestionExecutionResult(
        ingestion_run_id=1,
        data_source_id=uuid4(),
        status=status,
        records_fetched=4,
        records_inserted=3,
        records_skipped=1,
        error_message=None,
        metadata_json={},
    )


def test_structured_json_formatter_emits_machine_readable_payload():
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJsonFormatter())

    logger = logging.getLogger("tests.ingestion.runner.runtime")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info(
        "ingestion_runner_completed",
        extra={
            "event": "ingestion_runner_completed",
            "context": {
                "runner": "nasa_power",
                "status": IngestionRunStatus.SUCCEEDED,
                "records_inserted": 3,
            },
        },
    )

    payload = json.loads(stream.getvalue().strip())

    assert payload["event"] == "ingestion_runner_completed"
    assert payload["context"]["runner"] == "nasa_power"
    assert payload["context"]["status"] == "succeeded"
    assert payload["context"]["records_inserted"] == 3


def test_exit_code_helpers_cover_success_partial_and_failure_states():
    assert exit_code_for_run_status(IngestionRunStatus.SUCCEEDED) == RunnerExitCode.SUCCESS
    assert exit_code_for_run_status(IngestionRunStatus.PARTIAL) == RunnerExitCode.PARTIAL
    assert exit_code_for_run_status(IngestionRunStatus.FAILED) == RunnerExitCode.FAILURE
    assert exit_code_for_summary(failed_sources=0, partial_sources=1) == RunnerExitCode.PARTIAL
    assert exit_code_for_summary(failed_sources=1, partial_sources=0) == RunnerExitCode.FAILURE


def test_nasa_power_main_returns_partial_exit_code(monkeypatch):
    monkeypatch.setattr("app.ingestion.runners.run_nasa_power.settings.INGESTION_ENABLED_SOURCES", "")
    monkeypatch.setattr("app.ingestion.runners.run_nasa_power.settings.INGESTION_DISABLED_SOURCES", "")
    monkeypatch.setattr(
        "app.ingestion.runners.run_nasa_power.SessionLocal",
        lambda: _DummySession(),
    )
    monkeypatch.setattr(
        "app.ingestion.runners.run_nasa_power.execute_nasa_power_ingestion",
        lambda *args, **kwargs: _build_result(IngestionRunStatus.PARTIAL),
    )

    exit_code = nasa_power_main(["--days", "7", "--log-level", "ERROR"])

    assert exit_code == int(RunnerExitCode.PARTIAL)


def test_faostat_main_returns_configuration_error_exit_code(monkeypatch):
    monkeypatch.setattr("app.ingestion.runners.run_faostat.settings.INGESTION_ENABLED_SOURCES", "")
    monkeypatch.setattr("app.ingestion.runners.run_faostat.settings.INGESTION_DISABLED_SOURCES", "")
    monkeypatch.setattr(
        "app.ingestion.runners.run_faostat.SessionLocal",
        lambda: _DummySession(),
    )

    def raise_configuration_error(*args, **kwargs):
        raise ServiceValidationError("missing target table")

    monkeypatch.setattr(
        "app.ingestion.runners.run_faostat.execute_faostat_ingestion",
        raise_configuration_error,
    )

    exit_code = faostat_main(["--log-level", "ERROR"])

    assert exit_code == int(RunnerExitCode.CONFIGURATION_ERROR)
