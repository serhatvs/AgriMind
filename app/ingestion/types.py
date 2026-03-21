"""Shared types used across ingestion clients, transformers, validators, and runners."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, TypeAlias
from uuid import UUID

from app.models.enums import IngestionPayloadType, IngestionRunStatus


JSONScalar: TypeAlias = str | int | float | bool | None
JSONValue: TypeAlias = JSONScalar | dict[str, "JSONValue"] | list["JSONValue"]


@dataclass(frozen=True, slots=True)
class RawPayloadEnvelope:
    """Single raw payload fetched from an upstream source."""

    payload_type: IngestionPayloadType | str
    source_identifier: str
    raw_json: JSONValue


@dataclass(frozen=True, slots=True)
class NormalizedRecord:
    """Normalized record emitted by a transformer before validation and persistence."""

    record_type: str
    source_identifier: str
    values: Mapping[str, Any]
    payload_type: IngestionPayloadType | str


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """Validation issue found on a normalized record."""

    code: str
    message: str
    field_name: str | None = None

    def as_metadata(self) -> dict[str, JSONScalar]:
        """Serialize the issue into a JSON-safe metadata object."""

        return {
            "code": self.code,
            "message": self.message,
            "field_name": self.field_name,
        }


@dataclass(frozen=True, slots=True)
class SkippedRecord:
    """Single normalized row skipped during validation or deduplication."""

    source_identifier: str
    record_type: str
    stage: str
    reasons: tuple[ValidationIssue, ...]

    def as_metadata(self) -> dict[str, JSONValue]:
        """Serialize the skipped record into a JSON-safe metadata object."""

        return {
            "source_identifier": self.source_identifier,
            "record_type": self.record_type,
            "stage": self.stage,
            "reasons": [reason.as_metadata() for reason in self.reasons],
        }


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Batch validation outcome for a collection of normalized records."""

    valid_records: tuple[NormalizedRecord, ...] = ()
    skipped_records: tuple[SkippedRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedRow:
    """Normalized row prepared for insertion into a target table."""

    source_identifier: str
    record_type: str
    values: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class DeduplicationResult:
    """Outcome of duplicate filtering for prepared insertion rows."""

    unique_rows: tuple[PreparedRow, ...] = ()
    skipped_records: tuple[SkippedRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class PersistResult:
    """Persistence outcome for validated normalized records."""

    records_inserted: int = 0
    records_skipped: int = 0
    skipped_is_successful: bool = False
    skipped_records: tuple[SkippedRecord, ...] = ()
    metadata_json: dict[str, JSONValue] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class IngestionExecutionResult:
    """Summary returned when an ingestion pipeline completes."""

    ingestion_run_id: int
    data_source_id: UUID
    status: IngestionRunStatus
    records_fetched: int
    records_inserted: int
    records_skipped: int
    error_message: str | None
    metadata_json: dict[str, JSONValue]
