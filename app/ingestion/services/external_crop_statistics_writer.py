"""Duplicate-safe writer for normalized external crop statistics."""

from __future__ import annotations

from collections.abc import Sequence
import logging
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.reflection import reflect_tables
from app.ingestion.deduplication import (
    ExternalCropStatisticsDuplicateStrategy,
    collect_existing_keys,
    deduplicate_prepared_rows,
)
from app.ingestion.services.pipeline import NormalizedRecordWriter
from app.ingestion.types import NormalizedRecord, PersistResult, PreparedRow
from app.models.mixins import utc_now
from app.services.errors import ServiceValidationError


logger = logging.getLogger(__name__)


class ExternalCropStatisticsWriter(NormalizedRecordWriter):
    """Persist external crop statistics while skipping duplicate source/country/year/crop/stat rows."""

    def write(
        self,
        db: Session,
        records: Sequence[NormalizedRecord],
        *,
        data_source,
        ingestion_run,
    ) -> PersistResult:
        """Insert non-duplicate external crop statistics rows into the target table."""

        _ = (data_source, ingestion_run)
        if not records:
            return PersistResult(
                records_inserted=0,
                records_skipped=0,
                skipped_is_successful=True,
                metadata_json={"target_table": "external_crop_statistics", "duplicate_count": 0},
            )

        statistics_table = reflect_tables(db, "external_crop_statistics")["external_crop_statistics"]
        duplicate_strategy = ExternalCropStatisticsDuplicateStrategy()
        prepared_rows = [
            PreparedRow(
                source_identifier=record.source_identifier,
                record_type=record.record_type,
                values=self._build_insert_row(record),
            )
            for record in records
        ]

        existing_rows = db.execute(
            select(
                statistics_table.c.source_name,
                statistics_table.c.country,
                statistics_table.c.year,
                statistics_table.c.crop_name,
                statistics_table.c.statistic_type,
            )
            .where(statistics_table.c.source_name.in_({row.values["source_name"] for row in prepared_rows}))
            .where(statistics_table.c.country.in_({row.values["country"] for row in prepared_rows}))
            .where(statistics_table.c.year.in_({row.values["year"] for row in prepared_rows}))
            .where(statistics_table.c.crop_name.in_({row.values["crop_name"] for row in prepared_rows}))
        ).mappings()
        deduplication_result = deduplicate_prepared_rows(
            prepared_rows,
            existing_keys=collect_existing_keys(existing_rows, duplicate_strategy),
            strategy=duplicate_strategy,
        )
        insert_rows = [dict(row.values) for row in deduplication_result.unique_rows]
        duplicate_count = len(deduplication_result.skipped_records)

        if duplicate_count:
            logger.info("Skipping %s duplicate external crop statistics rows", duplicate_count)

        if insert_rows:
            try:
                db.execute(insert(statistics_table), insert_rows)
                db.commit()
            except SQLAlchemyError:
                db.rollback()
                raise

        return PersistResult(
            records_inserted=len(insert_rows),
            records_skipped=duplicate_count,
            skipped_is_successful=True,
            skipped_records=deduplication_result.skipped_records,
            metadata_json={
                "target_table": "external_crop_statistics",
                "duplicate_count": duplicate_count,
                "input_record_count": len(prepared_rows),
            },
        )

    def _build_insert_row(self, record: NormalizedRecord) -> dict[str, Any]:
        source_name = self._require_str(record.values.get("source_name"), "source_name", record.source_identifier)
        country = self._require_str(record.values.get("country"), "country", record.source_identifier)
        year = self._require_int(record.values.get("year"), "year", record.source_identifier)
        crop_name = self._require_str(record.values.get("crop_name"), "crop_name", record.source_identifier)
        statistic_type = self._require_str(
            record.values.get("statistic_type"),
            "statistic_type",
            record.source_identifier,
        )
        unit = self._require_str(record.values.get("unit"), "unit", record.source_identifier)

        return {
            "source_name": source_name,
            "country": country,
            "year": year,
            "crop_name": crop_name,
            "statistic_type": ExternalCropStatisticsDuplicateStrategy._normalize_statistic_type(statistic_type),
            "statistic_value": self._require_float(
                record.values.get("statistic_value"),
                "statistic_value",
                record.source_identifier,
            ),
            "unit": unit,
            "created_at": utc_now(),
        }

    @staticmethod
    def _require_str(value: Any, field_name: str, source_identifier: str) -> str:
        if value is None:
            raise ServiceValidationError(f"Record '{source_identifier}' is missing {field_name}")
        normalized_value = str(value).strip()
        if not normalized_value:
            raise ServiceValidationError(f"Record '{source_identifier}' is missing {field_name}")
        return normalized_value

    @staticmethod
    def _require_int(value: Any, field_name: str, source_identifier: str) -> int:
        if value is None:
            raise ServiceValidationError(f"Record '{source_identifier}' is missing {field_name}")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ServiceValidationError(
                f"Record '{source_identifier}' has an invalid {field_name}"
            ) from exc

    @staticmethod
    def _require_float(value: Any, field_name: str, source_identifier: str) -> float:
        if value is None:
            raise ServiceValidationError(f"Record '{source_identifier}' is missing {field_name}")
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ServiceValidationError(
                f"Record '{source_identifier}' has an invalid {field_name}"
            ) from exc
