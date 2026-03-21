"""Command-line runner for resetting NASA POWER ingestion audit and weather data."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from app.db import SessionLocal
from app.ingestion.runners.runtime import (
    RunnerExitCode,
    configure_runner_logging,
    exit_code_for_exception,
    log_event,
)
from app.ingestion.services.nasa_power_operations import reset_nasa_power_ingestion_data


logger = logging.getLogger(__name__)


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the NASA POWER reset runner."""

    parser = argparse.ArgumentParser(
        description="Delete NASA POWER weather_history rows and ingestion audit records.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Application log level.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for resetting NASA POWER ingestion state."""

    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    configure_runner_logging(args.log_level)

    db = SessionLocal()
    try:
        log_event(
            logger,
            logging.INFO,
            "nasa_power_reset_started",
            source_name="NASA POWER",
        )
        result = reset_nasa_power_ingestion_data(db)
        log_event(
            logger,
            logging.INFO,
            "nasa_power_reset_completed",
            source_name=result.source_name,
            data_source_id=result.data_source_id,
            stale_runs_marked=result.stale_runs_marked,
            weather_rows_deleted=result.weather_rows_deleted,
            raw_payloads_deleted=result.raw_payloads_deleted,
            ingestion_runs_deleted=result.ingestion_runs_deleted,
        )
        return int(RunnerExitCode.SUCCESS)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "nasa_power_reset_failed",
            source_name="NASA POWER",
            error_message=str(exc),
        )
        logger.exception("NASA POWER reset failed")
        return int(exit_code_for_exception(exc))
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
