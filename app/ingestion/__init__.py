"""Reusable ingestion foundation for source polling, validation, and persistence."""

from app.ingestion.types import (
    DeduplicationResult,
    IngestionExecutionResult,
    JSONValue,
    NormalizedRecord,
    PreparedRow,
    PersistResult,
    RawPayloadEnvelope,
    SkippedRecord,
    ValidationIssue,
    ValidationResult,
)

__all__ = [
    "DeduplicationResult",
    "IngestionExecutionResult",
    "JSONValue",
    "NormalizedRecord",
    "PreparedRow",
    "PersistResult",
    "RawPayloadEnvelope",
    "SkippedRecord",
    "ValidationIssue",
    "ValidationResult",
]
