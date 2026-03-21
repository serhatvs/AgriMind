"""Command-line runner for executing every configured ingestion source."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.ingestion.runners.runtime import (
    RunnerExitCode,
    configure_runner_logging,
    exit_code_for_summary,
    log_event,
)
from app.ingestion.runners.source_registry import (
    IngestionSourceRunnerRegistry,
    build_default_source_runner_registry,
)
from app.ingestion.services import IngestionRepository
from app.models.enums import IngestionRunType, IngestionRunStatus


logger = logging.getLogger(__name__)
SKIPPED_SOURCE_STATUS = "skipped"


@dataclass(frozen=True, slots=True)
class SourceRunReport:
    """Summary for a single source-specific ingestion execution."""

    source_name: str
    status: str
    records_fetched: int = 0
    records_inserted: int = 0
    records_skipped: int = 0
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RunAllSummary:
    """Aggregated summary across every executed ingestion source."""

    total_sources: int
    succeeded_sources: int
    partial_sources: int
    failed_sources: int
    skipped_sources: int
    reports: tuple[SourceRunReport, ...]


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the unified ingestion runner."""

    parser = argparse.ArgumentParser(
        description="Run every configured and active ingestion source.",
    )
    parser.add_argument(
        "--run-type",
        choices=[run_type.value for run_type in IngestionRunType],
        default=IngestionRunType.INCREMENTAL.value,
        help="Ingestion run classification recorded in ingestion_runs.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Application log level.",
    )
    return parser


def execute_all_ingestions(
    db: Session,
    *,
    run_type: IngestionRunType = IngestionRunType.INCREMENTAL,
    repository: IngestionRepository | None = None,
    registry: IngestionSourceRunnerRegistry | None = None,
    ensure_registered_sources: bool = True,
) -> RunAllSummary:
    """Run every active ingestion source registered in the source-runner registry."""

    repository = repository or IngestionRepository(db)
    repository.ensure_ingestion_tables_ready()
    registry = registry or build_default_source_runner_registry()

    if ensure_registered_sources:
        registry.ensure_registered_sources(repository)

    active_data_sources = repository.list_active_data_sources()
    log_event(
        logger,
        logging.INFO,
        "ingestion_run_all_discovered_sources",
        total_active_sources=len(active_data_sources),
    )

    reports: list[SourceRunReport] = []
    for data_source in active_data_sources:
        try:
            source_definition = registry.get(data_source.source_name)
        except KeyError as exc:
            error_message = str(exc)
            log_event(
                logger,
                logging.ERROR,
                "ingestion_source_failed",
                source_name=data_source.source_name,
                status=IngestionRunStatus.FAILED.value,
                error_message=error_message,
                reason="no_registered_runner",
            )
            reports.append(
                SourceRunReport(
                    source_name=data_source.source_name,
                    status=IngestionRunStatus.FAILED.value,
                    error_message=error_message,
                )
            )
            continue

        if not source_definition.is_enabled:
            log_event(
                logger,
                logging.INFO,
                "ingestion_source_skipped",
                source_name=data_source.source_name,
                reason="disabled_by_config",
            )
            reports.append(
                SourceRunReport(
                    source_name=data_source.source_name,
                    status=SKIPPED_SOURCE_STATUS,
                )
            )
            continue

        log_event(
            logger,
            logging.INFO,
            "ingestion_source_started",
            source_name=data_source.source_name,
            run_type=run_type,
        )
        try:
            result = source_definition.executor(
                db,
                run_type=run_type,
                repository=repository,
                data_source=data_source,
            )
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "ingestion_source_failed",
                source_name=data_source.source_name,
                status=IngestionRunStatus.FAILED.value,
                error_message=str(exc),
            )
            logger.exception("Ingestion source '%s' failed", data_source.source_name)
            reports.append(
                SourceRunReport(
                    source_name=data_source.source_name,
                    status=IngestionRunStatus.FAILED.value,
                    error_message=str(exc),
                )
            )
            continue

        reports.append(
            SourceRunReport(
                source_name=data_source.source_name,
                status=result.status.value,
                records_fetched=result.records_fetched,
                records_inserted=result.records_inserted,
                records_skipped=result.records_skipped,
                error_message=result.error_message,
            )
        )
        log_event(
            logger,
            logging.INFO,
            "ingestion_source_completed",
            source_name=data_source.source_name,
            status=result.status.value,
            records_fetched=result.records_fetched,
            records_inserted=result.records_inserted,
            records_skipped=result.records_skipped,
        )

    summary = _build_summary(reports)
    _log_summary(summary)
    return summary


def _build_summary(reports: Sequence[SourceRunReport]) -> RunAllSummary:
    succeeded_sources = sum(1 for report in reports if report.status == IngestionRunStatus.SUCCEEDED.value)
    partial_sources = sum(1 for report in reports if report.status == IngestionRunStatus.PARTIAL.value)
    failed_sources = sum(1 for report in reports if report.status == IngestionRunStatus.FAILED.value)
    skipped_sources = sum(1 for report in reports if report.status == SKIPPED_SOURCE_STATUS)
    return RunAllSummary(
        total_sources=len(reports),
        succeeded_sources=succeeded_sources,
        partial_sources=partial_sources,
        failed_sources=failed_sources,
        skipped_sources=skipped_sources,
        reports=tuple(reports),
    )


def _log_summary(summary: RunAllSummary) -> None:
    log_event(
        logger,
        logging.INFO,
        "ingestion_run_all_summary",
        total_sources=summary.total_sources,
        succeeded_sources=summary.succeeded_sources,
        partial_sources=summary.partial_sources,
        failed_sources=summary.failed_sources,
        skipped_sources=summary.skipped_sources,
    )
    for report in summary.reports:
        level = logging.ERROR if report.status == IngestionRunStatus.FAILED.value else logging.INFO
        log_event(
            logger,
            level,
            "ingestion_source_summary",
            source_name=report.source_name,
            status=report.status,
            records_fetched=report.records_fetched,
            records_inserted=report.records_inserted,
            records_skipped=report.records_skipped,
            error_message=report.error_message,
        )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for running every configured ingestion source."""

    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    configure_runner_logging(args.log_level)

    db = SessionLocal()
    try:
        log_event(
            logger,
            logging.INFO,
            "ingestion_run_all_started",
            run_type=args.run_type,
        )
        summary = execute_all_ingestions(
            db,
            run_type=IngestionRunType(args.run_type),
        )
        return int(
            exit_code_for_summary(
                failed_sources=summary.failed_sources,
                partial_sources=summary.partial_sources,
            )
        )
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "ingestion_run_all_failed",
            run_type=args.run_type,
            error_message=str(exc),
        )
        logger.exception("Unified ingestion runner failed")
        return int(RunnerExitCode.FAILURE)
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
