"""Validation abstractions for normalized ingestion records."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from app.ingestion.types import NormalizedRecord, SkippedRecord, ValidationIssue, ValidationResult


class RecordValidator(Protocol):
    """Protocol for validating normalized records before persistence."""

    def validate(self, record: NormalizedRecord) -> Sequence[ValidationIssue]:
        """Return validation issues for a normalized record."""


class CompositeRecordValidator:
    """Combine multiple validators into a single validation pass."""

    def __init__(self, validators: Iterable[RecordValidator] | None = None) -> None:
        self.validators = tuple(validators or ())

    def validate(self, record: NormalizedRecord) -> list[ValidationIssue]:
        """Run every configured validator and flatten their issues."""

        issues: list[ValidationIssue] = []
        for validator in self.validators:
            issues.extend(validator.validate(record))
        return issues


def validate_records(
    records: Sequence[NormalizedRecord],
    validators: Iterable[RecordValidator] | None = None,
) -> ValidationResult:
    """Split normalized records into valid and skipped groups with traceable reasons."""

    composite_validator = CompositeRecordValidator(validators)
    valid_records: list[NormalizedRecord] = []
    skipped_records: list[SkippedRecord] = []

    for record in records:
        issues = composite_validator.validate(record)
        if issues:
            skipped_records.append(
                SkippedRecord(
                    source_identifier=record.source_identifier,
                    record_type=record.record_type,
                    stage="validation",
                    reasons=tuple(issues),
                )
            )
            continue
        valid_records.append(record)

    return ValidationResult(
        valid_records=tuple(valid_records),
        skipped_records=tuple(skipped_records),
    )
