"""Command-line runner for verifying NASA POWER ingestion health."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from app.db import SessionLocal
from app.ingestion.errors import IngestionVerificationError
from app.ingestion.runners.runtime import (
    RunnerExitCode,
    configure_runner_logging,
    exit_code_for_exception,
    log_event,
)
from app.ingestion.services.nasa_power_operations import verify_nasa_power_ingestion


logger = logging.getLogger(__name__)


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the NASA POWER verification runner."""

    parser = argparse.ArgumentParser(
        description="Verify NASA POWER ingestion state and duplicate-safe rerun behavior.",
    )
    parser.add_argument(
        "--skip-rerun",
        action="store_true",
        help="Only validate the current database state without executing a duplicate-safe rerun.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        help="Application log level.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for verifying NASA POWER ingestion health."""

    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    configure_runner_logging(args.log_level)

    db = SessionLocal()
    try:
        log_event(
            logger,
            logging.INFO,
            "nasa_power_verification_started",
            source_name="NASA POWER",
            run_duplicate_safe_rerun=not args.skip_rerun,
        )
        result = verify_nasa_power_ingestion(
            db,
            run_duplicate_safe_rerun=not args.skip_rerun,
        )
        log_event(
            logger,
            logging.INFO,
            "nasa_power_verification_completed",
            source_name=result.source_name,
            data_source_id=result.data_source_id,
            succeeded_run_count=result.succeeded_run_count,
            raw_payload_count=result.raw_payload_count,
            weather_history_count=result.weather_history_count,
            duplicate_group_count=result.duplicate_group_count,
            rerun_ingestion_run_id=result.rerun_ingestion_run_id,
            rerun_status=result.rerun_status,
        )
        return int(RunnerExitCode.SUCCESS)
    except IngestionVerificationError as exc:
        log_event(
            logger,
            logging.ERROR,
            "nasa_power_verification_failed",
            source_name="NASA POWER",
            error_message=str(exc),
        )
        logger.error("NASA POWER verification failed: %s", exc)
        return int(RunnerExitCode.FAILURE)
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "nasa_power_verification_failed",
            source_name="NASA POWER",
            error_message=str(exc),
        )
        logger.exception("NASA POWER verification failed unexpectedly")
        return int(exit_code_for_exception(exc))
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
