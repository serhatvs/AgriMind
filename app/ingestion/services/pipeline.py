"""Generic ingestion pipeline that persists raw payloads and normalized records."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
import logging
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.ingestion.clients.base import IngestionClient
from app.ingestion.services.repository import IngestionRepository
from app.ingestion.transformers.base import PayloadTransformer
from app.ingestion.types import (
    IngestionExecutionResult,
    JSONValue,
    NormalizedRecord,
    PersistResult,
    SkippedRecord,
    ValidationIssue,
)
from app.ingestion.validators.base import RecordValidator, validate_records
from app.models.enums import IngestionRunStatus, IngestionRunType
from app.models.ingestion import DataSource, IngestionRun
from app.services.errors import ServiceValidationError


logger = logging.getLogger(__name__)


class NormalizedRecordWriter(Protocol):
    """Protocol for components that persist validated normalized records."""

    def write(
        self,
        db: Session,
        records: Sequence[NormalizedRecord],
        *,
        data_source: DataSource,
        ingestion_run: IngestionRun,
    ) -> PersistResult:
        """Persist normalized records and return insert/skip counters."""


class IngestionPipelineService:
    """Coordinate the generic ingestion flow for a single data source."""

    def __init__(
        self,
        db: Session,
        *,
        client: IngestionClient,
        transformer: PayloadTransformer,
        writer: NormalizedRecordWriter,
        validators: Iterable[RecordValidator] | None = None,
        repository: IngestionRepository | None = None,
        validation_issue_sample_limit: int = 20,
    ) -> None:
        self.db = db
        self.client = client
        self.transformer = transformer
        self.writer = writer
        self.validators = tuple(validators or ())
        self.repository = repository or IngestionRepository(db)
        self.validation_issue_sample_limit = validation_issue_sample_limit

    def run(
        self,
        data_source_id: UUID,
        *,
        run_type: IngestionRunType = IngestionRunType.FULL,
        metadata_json: dict[str, JSONValue] | None = None,
    ) -> IngestionExecutionResult:
        """Execute the ingestion flow for a single data source."""

        data_source = self.repository.get_required_data_source(data_source_id)
        if not data_source.is_active:
            raise ServiceValidationError(f"Data source '{data_source.source_name}' is inactive")

        stale_runs = self.repository.mark_stale_running_runs(
            data_source_id=data_source.id,
            stale_run_minutes=settings.INGESTION_STALE_RUN_MINUTES,
        )
        if stale_runs:
            logger.warning(
                "Marked %s stale ingestion run(s) before starting '%s'",
                len(stale_runs),
                data_source.source_name,
            )

        initial_metadata = {
            **dict(metadata_json or {}),
            "stale_runs_marked_before_start": len(stale_runs),
        }
        ingestion_run = self.repository.create_ingestion_run(
            data_source,
            run_type=run_type,
            metadata_json=initial_metadata,
        )

        records_fetched = 0
        records_inserted = 0
        records_skipped = 0
        validation_issues: list[ValidationIssue] = []
        validated_record_count = 0
        validation_skipped_records: list[SkippedRecord] = []
        finalized_run: IngestionRun | None = None
        terminal_exception: Exception | None = None

        try:
            payloads = list(self.client.fetch(data_source, run_type=run_type))
            records_fetched = len(payloads)
            if payloads:
                self.repository.store_raw_payloads(ingestion_run, payloads)

            validated_records: list[NormalizedRecord] = []
            for payload in payloads:
                if payload.is_error:
                    validation_skipped_records.append(
                        self._build_payload_skip_record(
                            payload=payload,
                            stage="fetch",
                            code="fetch_error",
                            message=payload.error_message or "Payload fetch failed",
                        )
                    )
                    records_skipped += 1
                    continue

                try:
                    transformed_records = self.transformer.transform(
                        payload,
                        data_source=data_source,
                        ingestion_run=ingestion_run,
                    )
                except Exception as exc:
                    validation_skipped_records.append(
                        self._build_payload_skip_record(
                            payload=payload,
                            stage="transformation",
                            code="transformation_error",
                            message=str(exc),
                        )
                    )
                    records_skipped += 1
                    continue
                validation_result = validate_records(transformed_records, self.validators)
                validated_records.extend(validation_result.valid_records)
                validation_skipped_records.extend(validation_result.skipped_records)
                for skipped_record in validation_result.skipped_records:
                    validation_issues.extend(skipped_record.reasons)
                records_skipped += len(validation_result.skipped_records)
            validated_record_count = len(validated_records)

            persist_result = self.writer.write(
                self.db,
                validated_records,
                data_source=data_source,
                ingestion_run=ingestion_run,
            )
            records_inserted = persist_result.records_inserted
            records_skipped += persist_result.records_skipped
            has_payload_stage_failures = bool(validation_skipped_records)
            has_validation_failures = bool(validation_issues)
            has_unexpected_writer_skips = (
                persist_result.records_skipped > 0 and not persist_result.skipped_is_successful
            )
            final_status = (
                IngestionRunStatus.PARTIAL
                if has_payload_stage_failures or has_validation_failures or has_unexpected_writer_skips
                else IngestionRunStatus.SUCCEEDED
            )
            run_metadata = self._build_run_metadata(
                initial_metadata=initial_metadata,
                validation_issues=validation_issues,
                validated_records=validated_record_count,
                skipped_records=tuple(validation_skipped_records) + persist_result.skipped_records,
                writer_metadata=persist_result.metadata_json,
            )
            finalized_run = self.repository.finalize_ingestion_run(
                ingestion_run,
                status=final_status,
                records_fetched=records_fetched,
                records_inserted=records_inserted,
                records_skipped=records_skipped,
                metadata_json=run_metadata,
            )
        except Exception as exc:
            terminal_exception = exc
            run_metadata = self._build_run_metadata(
                initial_metadata=initial_metadata,
                validation_issues=validation_issues,
                validated_records=validated_record_count,
                skipped_records=tuple(validation_skipped_records),
                writer_metadata=None,
            )
            raise
        finally:
            if finalized_run is None:
                run_metadata = self._build_run_metadata(
                    initial_metadata=initial_metadata,
                    validation_issues=validation_issues,
                    validated_records=validated_record_count,
                    skipped_records=tuple(validation_skipped_records),
                    writer_metadata=None,
                )
                failure_message = (
                    str(terminal_exception)
                    if terminal_exception is not None
                    else "Ingestion run exited without a terminal status."
                )
                try:
                    finalized_run = self.repository.finalize_ingestion_run(
                        ingestion_run,
                        status=IngestionRunStatus.FAILED,
                        records_fetched=records_fetched,
                        records_inserted=records_inserted,
                        records_skipped=records_skipped,
                        metadata_json=run_metadata,
                        error_message=failure_message,
                    )
                except Exception:
                    logger.exception(
                        "Failed to finalize ingestion run '%s' for source '%s'",
                        ingestion_run.id,
                        data_source.source_name,
                    )
                    raise

        return IngestionExecutionResult(
            ingestion_run_id=finalized_run.id,
            data_source_id=finalized_run.data_source_id,
            status=finalized_run.status,
            records_fetched=finalized_run.records_fetched,
            records_inserted=finalized_run.records_inserted,
            records_skipped=finalized_run.records_skipped,
            error_message=finalized_run.error_message,
            metadata_json=finalized_run.metadata_json,
        )

    def _build_run_metadata(
        self,
        *,
        initial_metadata: dict[str, JSONValue] | None,
        validation_issues: Sequence[ValidationIssue],
        validated_records: int,
        skipped_records: Sequence[SkippedRecord],
        writer_metadata: dict[str, JSONValue] | None,
    ) -> dict[str, JSONValue]:
        validation_issue_samples = [
            issue.as_metadata()
            for issue in validation_issues[: self.validation_issue_sample_limit]
        ]
        skipped_record_samples = [
            skipped_record.as_metadata()
            for skipped_record in skipped_records[: self.validation_issue_sample_limit]
        ]
        skip_reason_counts = Counter(
            issue.code
            for skipped_record in skipped_records
            for issue in skipped_record.reasons
        )
        return {
            **dict(initial_metadata or {}),
            "validated_record_count": validated_records,
            "validation_error_count": len(validation_issues),
            "validation_error_samples": validation_issue_samples,
            "skipped_record_count": len(skipped_records),
            "skip_record_samples": skipped_record_samples,
            "skip_reason_counts": dict(skip_reason_counts),
            **dict(writer_metadata or {}),
        }

    @staticmethod
    def _build_payload_skip_record(
        *,
        payload,
        stage: str,
        code: str,
        message: str,
    ) -> SkippedRecord:
        return SkippedRecord(
            source_identifier=payload.source_identifier,
            record_type="raw_payload",
            stage=stage,
            reasons=(
                ValidationIssue(
                    code=code,
                    message=message,
                ),
            ),
        )
