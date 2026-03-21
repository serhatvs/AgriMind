"""Command-line runner for FAOSTAT crop statistics ingestion."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.db.reflection import tables_exist
from app.ingestion.clients import FAOSTATBulkDownloadClient, FAOSTATIngestionClient
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
    bulk_client: FAOSTATBulkDownloadClient | None = None,
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
        source_type=DataSourceType.FILE,
        base_url=settings.FAOSTAT_BULK_DOWNLOAD_URL,
        default_is_active=True,
    )

    ingestion_client = FAOSTATIngestionClient(
        bulk_client=bulk_client or FAOSTATBulkDownloadClient(base_url=data_source.base_url),
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
        source_type=DataSourceType.FILE,
        base_url=settings.FAOSTAT_BULK_DOWNLOAD_URL,
        executor=execute_registered_faostat_ingestion,
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
    logging.basicConfig(
        level=getattr(logging, args.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    countries = parse_filter_values(args.country, settings.FAOSTAT_DEFAULT_COUNTRIES)
    crops = parse_filter_values(args.crop, settings.FAOSTAT_DEFAULT_CROPS)

    db = SessionLocal()
    try:
        execute_faostat_ingestion(
            db,
            start_year=args.start_year,
            end_year=args.end_year,
            countries=countries,
            crops=crops,
            batch_size=args.batch_size,
            run_type=IngestionRunType(args.run_type),
        )
    except Exception:
        logger.exception("FAOSTAT ingestion failed")
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
