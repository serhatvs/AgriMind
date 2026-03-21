"""Exports for reusable ingestion deduplication utilities."""

from app.ingestion.deduplication.base import DuplicateStrategy, collect_existing_keys, deduplicate_prepared_rows
from app.ingestion.deduplication.strategies import (
    ExternalCropStatisticsDuplicateStrategy,
    WeatherHistoryDuplicateStrategy,
)

__all__ = [
    "DuplicateStrategy",
    "ExternalCropStatisticsDuplicateStrategy",
    "WeatherHistoryDuplicateStrategy",
    "collect_existing_keys",
    "deduplicate_prepared_rows",
]
