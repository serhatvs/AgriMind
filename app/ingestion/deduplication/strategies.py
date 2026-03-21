"""Built-in duplicate strategies for ingestion target tables."""

from __future__ import annotations

from collections.abc import Hashable, Mapping
from typing import Any

from app.ingestion.types import ValidationIssue
from app.models.enums import ExternalCropStatisticType


class WeatherHistoryDuplicateStrategy:
    """Duplicate strategy for weather_history rows keyed by field and day."""

    def __init__(self, *, date_column_name: str) -> None:
        self.date_column_name = date_column_name

    def build_key(self, row: Mapping[str, Any]) -> Hashable:
        return (row["field_id"], row[self.date_column_name])

    def normalize_existing_key(self, row: Mapping[str, Any]) -> Hashable:
        return (row["field_id"], row[self.date_column_name])

    def build_duplicate_issue(self, row: Mapping[str, Any]) -> ValidationIssue:
        return ValidationIssue(
            code="duplicate_record",
            message=(
                "Duplicate weather_history row for "
                f"field_id={row['field_id']} and {self.date_column_name}={row[self.date_column_name]}"
            ),
            field_name=self.date_column_name,
        )


class ExternalCropStatisticsDuplicateStrategy:
    """Duplicate strategy for external crop statistics composite keys."""

    def build_key(self, row: Mapping[str, Any]) -> Hashable:
        return (
            str(row["country"]),
            int(row["year"]),
            str(row["crop_name"]),
            self._normalize_statistic_type(row["statistic_type"]),
        )

    def normalize_existing_key(self, row: Mapping[str, Any]) -> Hashable:
        return self.build_key(row)

    def build_duplicate_issue(self, row: Mapping[str, Any]) -> ValidationIssue:
        return ValidationIssue(
            code="duplicate_record",
            message=(
                "Duplicate external crop statistic for "
                f"{row['country']} / {row['year']} / "
                f"{row['crop_name']} / {self._normalize_statistic_type(row['statistic_type'])}"
            ),
            field_name="statistic_type",
        )

    @staticmethod
    def _normalize_statistic_type(value: Any) -> str:
        if isinstance(value, ExternalCropStatisticType):
            return value.value

        normalized_value = str(value).strip()
        if normalized_value in ExternalCropStatisticType.__members__:
            return ExternalCropStatisticType[normalized_value].value

        try:
            return ExternalCropStatisticType(normalized_value).value
        except ValueError:
            return normalized_value
