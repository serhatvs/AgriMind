"""Validator for normalized weather_history ingestion records."""

from __future__ import annotations

from datetime import date
import logging

from app.ingestion.types import NormalizedRecord, ValidationIssue
from app.ingestion.validators.base import CompositeRecordValidator
from app.ingestion.validators.required_fields import RequiredFieldsValidator
from app.ingestion.validators.rules import FieldTypeValidator, NumericRangeValidator, PredicateValidator


logger = logging.getLogger(__name__)


class WeatherHistoryRecordValidator:
    """Validate normalized weather rows before persistence."""

    def __init__(self) -> None:
        self.validator = CompositeRecordValidator(
            (
                RequiredFieldsValidator(
                    "field_id",
                    "weather_date",
                    "min_temp",
                    "max_temp",
                    "avg_temp",
                    "rainfall_mm",
                    "humidity",
                    "wind_speed",
                ),
                FieldTypeValidator(("weather_date", "date"), date, field_label="weather_date"),
                NumericRangeValidator("rainfall_mm", min_value=0),
                NumericRangeValidator("humidity", min_value=0, max_value=100),
                NumericRangeValidator("wind_speed", min_value=0),
                NumericRangeValidator("solar_radiation", min_value=0, allow_none=True),
                NumericRangeValidator("et0", min_value=0, allow_none=True),
                PredicateValidator(
                    self._temperatures_are_ordered,
                    code="invalid_temperature_order",
                    message="Temperature values must satisfy min_temp <= avg_temp <= max_temp",
                    field_name="avg_temp",
                ),
            )
        )

    def validate(self, record: NormalizedRecord) -> list[ValidationIssue]:
        """Return validation issues for a weather history record."""

        issues = self.validator.validate(record)
        if issues:
            logger.warning(
                "Skipping invalid weather record '%s' due to %s issue(s)",
                record.source_identifier,
                len(issues),
            )
        return issues

    @staticmethod
    def _temperatures_are_ordered(record: NormalizedRecord) -> bool:
        min_temp = record.values.get("min_temp")
        avg_temp = record.values.get("avg_temp")
        max_temp = record.values.get("max_temp")
        if None in (min_temp, avg_temp, max_temp):
            return True
        if not all(isinstance(value, (int, float)) for value in (min_temp, avg_temp, max_temp)):
            return True
        return float(min_temp) <= float(avg_temp) <= float(max_temp)
