"""Reusable validator for required normalized record fields."""

from __future__ import annotations

from app.ingestion.types import NormalizedRecord, ValidationIssue


class RequiredFieldsValidator:
    """Reject records that omit required fields or provide blank values."""

    def __init__(self, *required_fields: str) -> None:
        self.required_fields = tuple(required_fields)

    def validate(self, record: NormalizedRecord) -> list[ValidationIssue]:
        """Return issues for missing or blank required field values."""

        issues: list[ValidationIssue] = []
        for field_name in self.required_fields:
            value = record.values.get(field_name)
            if value is None or value == "":
                issues.append(
                    ValidationIssue(
                        code="missing_required_field",
                        message=f"Field '{field_name}' is required",
                        field_name=field_name,
                    )
                )
        return issues
