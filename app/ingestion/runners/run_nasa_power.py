"""Command-line runner for NASA POWER daily weather ingestion."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from datetime import date

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.ingestion.clients import NASAPowerAPIClient, NASAPowerIngestionClient
from app.ingestion.runners.source_registry import IngestionSourceDefinition
from app.ingestion.services import (
    FieldCoordinateService,
    IngestionPipelineService,
    IngestionRepository,
    WeatherHistoryIngestionWriter,
)
from app.ingestion.transformers import NASAPowerWeatherTransformer
from app.ingestion.types import IngestionExecutionResult
from app.ingestion.validators import WeatherHistoryRecordValidator
from app.models.enums import DataSourceType, IngestionRunType
from app.models.ingestion import DataSource


logger = logging.getLogger(__name__)


def parse_iso_date(value: str) -> date:
    """Parse an ISO-8601 date argument for the NASA POWER runner CLI."""

    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid ISO date: {value}") from exc


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the NASA POWER ingestion module."""

    parser = argparse.ArgumentParser(
        description="Fetch daily field weather from NASA POWER and persist it into weather_history.",
    )
    parser.add_argument("--start-date", type=parse_iso_date, help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", type=parse_iso_date, help="Inclusive end date in YYYY-MM-DD format.")
    parser.add_argument(
        "--days",
        type=int,
        default=settings.NASA_POWER_DEFAULT_LOOKBACK_DAYS,
        help="Look back this many days when start_date is omitted.",
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


def execute_nasa_power_ingestion(
    db: Session,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    days: int | None = None,
    run_type: IngestionRunType = IngestionRunType.INCREMENTAL,
    repository: IngestionRepository | None = None,
    field_service: FieldCoordinateService | None = None,
    api_client: NASAPowerAPIClient | None = None,
    data_source: DataSource | None = None,
) -> IngestionExecutionResult:
    """Run the NASA POWER ingestion flow for all fields that have coordinates."""

    if days is not None and days <= 0:
        raise ValueError("days must be greater than 0")

    repository = repository or IngestionRepository(db)
    repository.ensure_ingestion_tables_ready()

    data_source = data_source or repository.ensure_registered_data_source(
        source_name=settings.NASA_POWER_SOURCE_NAME,
        source_type=DataSourceType.API,
        base_url=settings.NASA_POWER_BASE_URL,
        default_is_active=True,
    )

    field_service = field_service or FieldCoordinateService(db)
    field_targets = field_service.list_fields_with_coordinates()
    if not field_targets:
        logger.warning("NASA POWER ingestion found no fields with coordinates")

    pipeline_client = NASAPowerIngestionClient(
        api_client=api_client or NASAPowerAPIClient(base_url=data_source.base_url),
        field_targets=field_targets,
        start_date=start_date,
        end_date=end_date,
        default_lookback_days=days,
    )
    resolved_start_date, resolved_end_date = pipeline_client.resolve_date_range()

    pipeline = IngestionPipelineService(
        db,
        client=pipeline_client,
        transformer=NASAPowerWeatherTransformer(),
        writer=WeatherHistoryIngestionWriter(),
        validators=[WeatherHistoryRecordValidator()],
        repository=repository,
    )
    result = pipeline.run(
        data_source.id,
        run_type=run_type,
        metadata_json={
            "source_name": data_source.source_name,
            "source_type": data_source.source_type.value,
            "field_target_count": len(field_targets),
            "start_date": resolved_start_date.isoformat(),
            "end_date": resolved_end_date.isoformat(),
        },
    )
    logger.info(
        "NASA POWER ingestion finished with status=%s fetched=%s inserted=%s skipped=%s",
        result.status.value,
        result.records_fetched,
        result.records_inserted,
        result.records_skipped,
    )
    return result


def execute_registered_nasa_power_ingestion(
    db: Session,
    *,
    run_type: IngestionRunType,
    repository: IngestionRepository,
    data_source: DataSource,
) -> IngestionExecutionResult:
    """Execute NASA POWER ingestion for a registry-provided data source row."""

    return execute_nasa_power_ingestion(
        db,
        run_type=run_type,
        repository=repository,
        data_source=data_source,
    )


def build_nasa_power_source_definition() -> IngestionSourceDefinition:
    """Return the built-in source registration for NASA POWER."""

    return IngestionSourceDefinition(
        source_name=settings.NASA_POWER_SOURCE_NAME,
        source_type=DataSourceType.API,
        base_url=settings.NASA_POWER_BASE_URL,
        executor=execute_registered_nasa_power_ingestion,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint for running the NASA POWER ingestion job."""

    parser = build_argument_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    logging.basicConfig(
        level=getattr(logging, args.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db = SessionLocal()
    try:
        execute_nasa_power_ingestion(
            db,
            start_date=args.start_date,
            end_date=args.end_date,
            days=args.days,
            run_type=IngestionRunType(args.run_type),
        )
    except Exception:
        logger.exception("NASA POWER ingestion failed")
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
