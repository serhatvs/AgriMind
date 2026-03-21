"""Reusable deduplication helpers for prepared ingestion rows."""

from __future__ import annotations

from collections.abc import Hashable, Iterable, Mapping, Sequence
from typing import Any, Protocol

from app.ingestion.types import DeduplicationResult, PreparedRow, SkippedRecord, ValidationIssue


class DuplicateStrategy(Protocol):
    """Protocol for building stable duplicate keys across ingestion sources."""

    def build_key(self, row: Mapping[str, Any]) -> Hashable:
        """Return the deduplication key for a prepared row."""

    def normalize_existing_key(self, row: Mapping[str, Any]) -> Hashable:
        """Return the deduplication key for an already persisted row."""

    def build_duplicate_issue(self, row: Mapping[str, Any]) -> ValidationIssue:
        """Return a traceable reason for skipping a duplicate row."""


def collect_existing_keys(
    existing_rows: Iterable[Mapping[str, Any]],
    strategy: DuplicateStrategy,
) -> set[Hashable]:
    """Normalize a collection of persisted rows into comparable duplicate keys."""

    return {strategy.normalize_existing_key(row) for row in existing_rows}


def deduplicate_prepared_rows(
    rows: Sequence[PreparedRow],
    *,
    existing_keys: Iterable[Hashable],
    strategy: DuplicateStrategy,
) -> DeduplicationResult:
    """Split prepared rows into unique rows and duplicates with traceable reasons."""

    seen_keys = set(existing_keys)
    unique_rows: list[PreparedRow] = []
    skipped_records: list[SkippedRecord] = []

    for row in rows:
        row_key = strategy.build_key(row.values)
        if row_key in seen_keys:
            skipped_records.append(
                SkippedRecord(
                    source_identifier=row.source_identifier,
                    record_type=row.record_type,
                    stage="deduplication",
                    reasons=(strategy.build_duplicate_issue(row.values),),
                )
            )
            continue

        seen_keys.add(row_key)
        unique_rows.append(row)

    return DeduplicationResult(
        unique_rows=tuple(unique_rows),
        skipped_records=tuple(skipped_records),
    )
