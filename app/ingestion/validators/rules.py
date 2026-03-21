"""Reusable field and record validation rules for normalized ingestion rows."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
import math
from typing import Any

from app.ingestion.types import NormalizedRecord, ValidationIssue


FieldSelector = str | Sequence[str]


def _normalize_field_names(field_names: FieldSelector) -> tuple[str, ...]:
    if isinstance(field_names, str):
        return (field_names,)
    return tuple(field_names)


def _field_label(field_names: tuple[str, ...], field_label: str | None = None) -> str:
    return field_label or "/".join(field_names)


def _select_field_value(values: Mapping[str, Any], field_names: tuple[str, ...]) -> tuple[str, Any, bool]:
    for field_name in field_names:
        if field_name in values:
            return field_name, values[field_name], True
    return field_names[0], None, False


class FieldTypeValidator:
    """Validate that a field contains a value of the expected Python type."""

    def __init__(
        self,
        field_names: FieldSelector,
        expected_types: type[Any] | tuple[type[Any], ...],
        *,
        allow_none: bool = True,
        field_label: str | None = None,
        code: str = "invalid_type",
        message: str | None = None,
    ) -> None:
        self.field_names = _normalize_field_names(field_names)
        self.expected_types = expected_types
        self.allow_none = allow_none
        self.field_label = _field_label(self.field_names, field_label)
        self.code = code
        self.message = message

    def validate(self, record: NormalizedRecord) -> list[ValidationIssue]:
        """Return an issue when the selected field exists but has the wrong type."""

        field_name, value, present = _select_field_value(record.values, self.field_names)
        if not present or value is None:
            return [] if self.allow_none else [
                ValidationIssue(
                    code=self.code,
                    message=self.message or f"Field '{self.field_label}' must not be null",
                    field_name=self.field_label,
                )
            ]

        if isinstance(value, self.expected_types):
            return []

        expected_type_names = self._expected_type_names()
        return [
            ValidationIssue(
                code=self.code,
                message=self.message or f"Field '{self.field_label}' must be of type {expected_type_names}",
                field_name=field_name,
            )
        ]

    def _expected_type_names(self) -> str:
        if isinstance(self.expected_types, tuple):
            return ", ".join(expected_type.__name__ for expected_type in self.expected_types)
        return self.expected_types.__name__


class NumericRangeValidator:
    """Validate that a numeric field is finite and falls within an expected range."""

    def __init__(
        self,
        field_names: FieldSelector,
        *,
        min_value: float | None = None,
        max_value: float | None = None,
        allow_none: bool = True,
        require_finite: bool = True,
        field_label: str | None = None,
    ) -> None:
        self.field_names = _normalize_field_names(field_names)
        self.min_value = min_value
        self.max_value = max_value
        self.allow_none = allow_none
        self.require_finite = require_finite
        self.field_label = _field_label(self.field_names, field_label)

    def validate(self, record: NormalizedRecord) -> list[ValidationIssue]:
        """Return issues when a numeric field is missing, invalid, or out of range."""

        field_name, value, present = _select_field_value(record.values, self.field_names)
        if not present or value is None:
            return [] if self.allow_none else [
                ValidationIssue(
                    code="missing_required_field",
                    message=f"Field '{self.field_label}' is required",
                    field_name=self.field_label,
                )
            ]

        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [
                ValidationIssue(
                    code="invalid_numeric_type",
                    message=f"Field '{self.field_label}' must be numeric",
                    field_name=field_name,
                )
            ]

        numeric_value = float(value)
        if self.require_finite and not math.isfinite(numeric_value):
            return [
                ValidationIssue(
                    code="invalid_numeric_value",
                    message=f"Field '{self.field_label}' must be finite",
                    field_name=field_name,
                )
            ]

        issues: list[ValidationIssue] = []
        if self.min_value is not None and numeric_value < self.min_value:
            issues.append(
                ValidationIssue(
                    code="value_below_minimum",
                    message=f"Field '{self.field_label}' must be >= {self.min_value}",
                    field_name=field_name,
                )
            )
        if self.max_value is not None and numeric_value > self.max_value:
            issues.append(
                ValidationIssue(
                    code="value_above_maximum",
                    message=f"Field '{self.field_label}' must be <= {self.max_value}",
                    field_name=field_name,
                )
            )
        return issues


class AllowedValuesValidator:
    """Validate that a field value belongs to a configured set of allowed values."""

    def __init__(
        self,
        field_names: FieldSelector,
        allowed_values: Iterable[Any],
        *,
        allow_none: bool = True,
        field_label: str | None = None,
        normalizer: Callable[[Any], Any] | None = None,
        code: str = "invalid_allowed_value",
        message: str | None = None,
    ) -> None:
        self.field_names = _normalize_field_names(field_names)
        self.field_label = _field_label(self.field_names, field_label)
        self.allow_none = allow_none
        self.normalizer = normalizer or (lambda value: value)
        self.allowed_values = {self.normalizer(value) for value in allowed_values}
        self.code = code
        self.message = message

    def validate(self, record: NormalizedRecord) -> list[ValidationIssue]:
        """Return an issue when the selected field is not in the allowed set."""

        field_name, value, present = _select_field_value(record.values, self.field_names)
        if not present or value is None:
            return [] if self.allow_none else [
                ValidationIssue(
                    code="missing_required_field",
                    message=f"Field '{self.field_label}' is required",
                    field_name=self.field_label,
                )
            ]

        normalized_value = self.normalizer(value)
        if normalized_value in self.allowed_values:
            return []

        return [
            ValidationIssue(
                code=self.code,
                message=self.message or f"Field '{self.field_label}' is not supported",
                field_name=field_name,
            )
        ]


class PredicateValidator:
    """Validate a whole record using a custom boolean predicate."""

    def __init__(
        self,
        predicate: Callable[[NormalizedRecord], bool],
        *,
        code: str,
        message: str,
        field_name: str | None = None,
    ) -> None:
        self.predicate = predicate
        self.code = code
        self.message = message
        self.field_name = field_name

    def validate(self, record: NormalizedRecord) -> list[ValidationIssue]:
        """Return an issue when the configured predicate fails."""

        if self.predicate(record):
            return []
        return [
            ValidationIssue(
                code=self.code,
                message=self.message,
                field_name=self.field_name,
            )
        ]
