"""Command-line runner for FAOSTAT crop statistics ingestion."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.db.reflection import tables_exist
from app.ingestion.clients import FAOSTATAPIClient, FAOSTATIngestionClient
from app.ingestion.runners.runtime import (
    RunnerExitCode,
    configure_runner_logging,
    exit_code_for_exception,
    exit_code_for_run_status,
    log_event,
)
from app.ingestion.runners.source_registry import IngestionSourceDefinition
from app.ingestion.services import (
    ExternalCropStatisticsWriter,
    IngestionPipelineService,
    IngestionRepository,
)
from app.ingestion.transformers import FAOSTATStatisticsTransformer
from app.ingestion.types import IngestionExecutionResult
from app.ingestion.validators import ExternalCropStatisticsValidator
from app.models.enums import DataSourceType, IngestionRunType
from app.models.ingestion import DataSource
from app.services.errors import ServiceValidationError


logger = logging.getLogger(__name__)


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the FAOSTAT ingestion module."""

    parser = argparse.ArgumentParser(
        description="Fetch annual crop statistics from FAOSTAT and persist them internally.",
    )
    parser.add_argument("--start-year", type=int, help="Inclusive start year.")
    parser.add_argument("--end-year", type=int, help="Inclusive end year.")
    parser.add_argument(
        "--country",
        action="append",
        default=None,
        help="Country filter. Repeat or pass comma-separated values.",
    )
    parser.add_argument(
        "--crop",
        action="append",
        default=None,
        help="Crop filter. Repeat or pass comma-separated values.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=settings.FAOSTAT_BATCH_SIZE,
        help="Number of raw FAOSTAT rows stored per raw payload envelope.",
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


def execute_faostat_ingestion(
    db: Session,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    countries: Sequence[str] | None = None,
    crops: Sequence[str] | None = None,
    batch_size: int | None = None,
    run_type: IngestionRunType = IngestionRunType.INCREMENTAL,
    repository: IngestionRepository | None = None,
    api_client: FAOSTATAPIClient | None = None,
    data_source: DataSource | None = None,
) -> IngestionExecutionResult:
    """Run the FAOSTAT ingestion flow for annual crop statistics."""

    repository = repository or IngestionRepository(db)
    repository.ensure_ingestion_tables_ready()
    if not tables_exist(db, "external_crop_statistics"):
        raise ServiceValidationError(
            "Target table 'external_crop_statistics' is missing. Run 'alembic upgrade head' before FAOSTAT ingestion."
        )

    data_source = data_source or repository.ensure_registered_data_source(
        source_name=settings.FAOSTAT_SOURCE_NAME,
        source_type=DataSourceType.API,
        base_url=settings.FAOSTAT_API_BASE_URL,
        default_is_active=True,
    )

    ingestion_client = FAOSTATIngestionClient(
        api_client=api_client or FAOSTATAPIClient(base_url=data_source.base_url),
        start_year=start_year,
        end_year=end_year,
        countries=countries,
        crops=crops,
        batch_size=batch_size,
    )
    resolved_start_year, resolved_end_year = ingestion_client.resolve_year_range()

    pipeline = IngestionPipelineService(
        db,
        client=ingestion_client,
        transformer=FAOSTATStatisticsTransformer(),
        writer=ExternalCropStatisticsWriter(),
        validators=[ExternalCropStatisticsValidator()],
        repository=repository,
    )
    result = pipeline.run(
        data_source.id,
        run_type=run_type,
        metadata_json={
            "source_name": data_source.source_name,
            "source_type": data_source.source_type.value,
            "start_year": resolved_start_year,
            "end_year": resolved_end_year,
            "country_filters": list(countries or ()),
            "crop_filters": list(crops or ()),
            "batch_size": ingestion_client.batch_size,
        },
    )
    logger.info(
        "FAOSTAT ingestion finished with status=%s fetched=%s inserted=%s skipped=%s",
        result.status.value,
        result.records_fetched,
        result.records_inserted,
        result.records_skipped,
    )
    return result


def execute_registered_faostat_ingestion(
    db: Session,
    *,
    run_type: IngestionRunType,
    repository: IngestionRepository,
    data_source: DataSource,
) -> IngestionExecutionResult:
    """Execute FAOSTAT ingestion for a registry-provided data source row."""

    return execute_faostat_ingestion(
        db,
        run_type=run_type,
        repository=repository,
        data_source=data_source,
    )


def build_faostat_source_definition() -> IngestionSourceDefinition:
    """Return the built-in source registration for FAOSTAT."""

    return IngestionSourceDefinition(
        source_name=settings.FAOSTAT_SOURCE_NAME,
        source_type=DataSourceType.API,
        base_url=settings.FAOSTAT_API_BASE_URL,
        executor=execute_registered_faostat_ingestion,
        default_is_active=settings.is_ingestion_source_enabled(settings.FAOSTAT_SOURCE_NAME),
        is_enabled=settings.is_ingestion_source_enabled(settings.FAOSTAT_SOURCE_NAME),
    )


def parse_filter_values(values: Sequence[str] | None, default_csv: str) -> list[str]:
    """Parse repeated or comma-separated CLI values into a clean string list."""

    input_values = list(values or ())
    if not input_values and default_csv.strip():
        input_values = [default_csv]

    parsed_values: list[str] = []
    for value in input_values:
        for part in value.split(","):
            cleaned = part.strip()
            if cleaned:
                parsed_values.append(cleaned)
    return parsed_values


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for running the FAOSTAT ingestion job."""

    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    configure_runner_logging(args.log_level)

    countries = parse_filter_values(args.country, settings.FAOSTAT_DEFAULT_COUNTRIES)
    crops = parse_filter_values(args.crop, settings.FAOSTAT_DEFAULT_CROPS)
    source_definition = build_faostat_source_definition()

    if not source_definition.is_enabled:
        log_event(
            logger,
            logging.INFO,
            "ingestion_runner_skipped",
            runner="faostat",
            source_name=source_definition.source_name,
            reason="disabled_by_config",
        )
        return int(RunnerExitCode.SUCCESS)

    db = SessionLocal()
    try:
        log_event(
            logger,
            logging.INFO,
            "ingestion_runner_started",
            runner="faostat",
            source_name=source_definition.source_name,
            run_type=args.run_type,
            start_year=args.start_year,
            end_year=args.end_year,
            countries=countries,
            crops=crops,
            batch_size=args.batch_size,
        )
        result = execute_faostat_ingestion(
            db,
            start_year=args.start_year,
            end_year=args.end_year,
            countries=countries,
            crops=crops,
            batch_size=args.batch_size,
            run_type=IngestionRunType(args.run_type),
        )
        log_event(
            logger,
            logging.INFO,
            "ingestion_runner_completed",
            runner="faostat",
            source_name=source_definition.source_name,
            status=result.status,
            records_fetched=result.records_fetched,
            records_inserted=result.records_inserted,
            records_skipped=result.records_skipped,
            ingestion_run_id=result.ingestion_run_id,
        )
        return int(exit_code_for_run_status(result.status))
    except Exception as exc:
        log_event(
            logger,
            logging.ERROR,
            "ingestion_runner_failed",
            runner="faostat",
            source_name=source_definition.source_name,
            error_message=str(exc),
        )
        logger.exception("FAOSTAT ingestion failed")
        return int(exit_code_for_exception(exc))
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
