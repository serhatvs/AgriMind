"""Validator for normalized external crop statistics records."""

from __future__ import annotations

import logging

from app.ingestion.types import NormalizedRecord, ValidationIssue
from app.ingestion.validators.base import CompositeRecordValidator
from app.ingestion.validators.required_fields import RequiredFieldsValidator
from app.ingestion.validators.rules import AllowedValuesValidator, FieldTypeValidator, NumericRangeValidator
from app.models.enums import ExternalCropStatisticType


logger = logging.getLogger(__name__)


class ExternalCropStatisticsValidator:
    """Validate normalized annual crop statistic records before persistence."""

    def __init__(self) -> None:
        self.validator = CompositeRecordValidator(
            (
                RequiredFieldsValidator(
                    "source_name",
                    "country",
                    "year",
                    "crop_name",
                    "statistic_type",
                    "statistic_value",
                    "unit",
                ),
                FieldTypeValidator("year", int),
                FieldTypeValidator("statistic_value", (int, float)),
                NumericRangeValidator("year", min_value=1900),
                NumericRangeValidator("statistic_value", min_value=0),
                AllowedValuesValidator(
                    "statistic_type",
                    (statistic_type.value for statistic_type in ExternalCropStatisticType),
                    code="invalid_statistic_type",
                    message="statistic_type is not supported",
                    normalizer=lambda value: str(getattr(value, "value", value)).lower(),
                ),
            )
        )

    def validate(self, record: NormalizedRecord) -> list[ValidationIssue]:
        """Return validation issues for an external crop statistics record."""

        issues = self.validator.validate(record)
        if issues:
            logger.warning(
                "Skipping invalid external crop statistic '%s' due to %s issue(s)",
                record.source_identifier,
                len(issues),
            )
        return issues
