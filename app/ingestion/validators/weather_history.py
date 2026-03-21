"""Validator for normalized weather_history ingestion records."""

from __future__ import annotations

from datetime import date, timedelta
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
                ),
                FieldTypeValidator(("weather_date", "date"), date, field_label="weather_date"),
                NumericRangeValidator("min_temp", min_value=-80, max_value=70, allow_none=True),
                NumericRangeValidator("max_temp", min_value=-80, max_value=75, allow_none=True),
                NumericRangeValidator("avg_temp", min_value=-80, max_value=75, allow_none=True),
                NumericRangeValidator("rainfall_mm", min_value=0, max_value=1000, allow_none=True),
                NumericRangeValidator("humidity", min_value=0, max_value=100, allow_none=True),
                NumericRangeValidator("wind_speed", min_value=0, max_value=200, allow_none=True),
                NumericRangeValidator("solar_radiation", min_value=0, max_value=100, allow_none=True),
                NumericRangeValidator("et0", min_value=0, allow_none=True),
                PredicateValidator(
                    self._weather_date_is_reasonable,
                    code="invalid_weather_date",
                    message="weather_date must be within a sane historical range",
                    field_name="weather_date",
                ),
                PredicateValidator(
                    self._has_any_observation_metric,
                    code="missing_weather_observation",
                    message="At least one weather metric must be present",
                    field_name="weather_date",
                ),
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

    @staticmethod
    def _weather_date_is_reasonable(record: NormalizedRecord) -> bool:
        weather_date = record.values.get("weather_date")
        if not isinstance(weather_date, date):
            return True
        return date(1980, 1, 1) <= weather_date <= (date.today() + timedelta(days=1))

    @staticmethod
    def _has_any_observation_metric(record: NormalizedRecord) -> bool:
        metric_names = (
            "min_temp",
            "max_temp",
            "avg_temp",
            "rainfall_mm",
            "humidity",
            "wind_speed",
            "solar_radiation",
            "et0",
        )
        return any(record.values.get(metric_name) is not None for metric_name in metric_names)
