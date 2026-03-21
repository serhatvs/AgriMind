"""Resolve explicit or inferred crop climate requirements for scoring."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


@dataclass(frozen=True, slots=True)
class CropClimateRequirements:
    """Resolved crop climate requirements used by climate scoring and explanations."""

    optimal_temp_min_c: float | None
    optimal_temp_max_c: float | None
    tolerable_temp_min_c: float | None
    tolerable_temp_max_c: float | None
    preferred_rainfall_min_mm: float | None
    preferred_rainfall_max_mm: float | None
    frost_tolerance_days: int | None
    heat_tolerance_days: int | None
    source: str


_NAMED_CROP_DEFAULTS: dict[str, CropClimateRequirements] = {
    "blackberry": CropClimateRequirements(16.0, 27.0, 8.0, 34.0, 55.0, 110.0, 4, 8, "named_default"),
    "corn": CropClimateRequirements(18.0, 30.0, 10.0, 36.0, 80.0, 140.0, 1, 8, "named_default"),
    "wheat": CropClimateRequirements(12.0, 24.0, 4.0, 30.0, 45.0, 95.0, 6, 6, "named_default"),
    "sunflower": CropClimateRequirements(20.0, 32.0, 12.0, 38.0, 35.0, 80.0, 2, 12, "named_default"),
    "chickpea": CropClimateRequirements(16.0, 28.0, 8.0, 34.0, 30.0, 75.0, 3, 9, "named_default"),
}
_WATER_REQUIREMENT_RAINFALL_DEFAULTS: dict[str, tuple[float, float]] = {
    "low": (30.0, 75.0),
    "medium": (50.0, 110.0),
    "high": (80.0, 140.0),
}
_SENSITIVITY_TOLERANCE_DEFAULTS: dict[str, int] = {
    "high": 1,
    "medium": 4,
    "low": 8,
}


def resolve_crop_climate_requirements(crop: Any) -> CropClimateRequirements:
    """Return explicit crop climate requirements or inferred fallbacks."""

    optimal_temp_min_c = _coerce_float(
        _first_not_none(
            getattr(crop, "optimal_temp_min_c", None),
            getattr(crop, "optimal_temp_min", None),
        )
    )
    optimal_temp_max_c = _coerce_float(
        _first_not_none(
            getattr(crop, "optimal_temp_max_c", None),
            getattr(crop, "optimal_temp_max", None),
        )
    )
    tolerable_temp_min_c = _coerce_float(
        _first_not_none(
            getattr(crop, "tolerable_temp_min_c", None),
            getattr(crop, "tolerable_temp_min", None),
        )
    )
    tolerable_temp_max_c = _coerce_float(
        _first_not_none(
            getattr(crop, "tolerable_temp_max_c", None),
            getattr(crop, "tolerable_temp_max", None),
        )
    )
    preferred_rainfall_min_mm = _coerce_float(
        _first_not_none(
            getattr(crop, "preferred_rainfall_min_mm", None),
            getattr(crop, "preferred_rainfall_min", None),
        )
    )
    preferred_rainfall_max_mm = _coerce_float(
        _first_not_none(
            getattr(crop, "preferred_rainfall_max_mm", None),
            getattr(crop, "preferred_rainfall_max", None),
        )
    )
    frost_tolerance_days = _coerce_int(
        _first_not_none(
            getattr(crop, "frost_tolerance_days", None),
            getattr(crop, "frost_tolerance", None),
        )
    )
    heat_tolerance_days = _coerce_int(
        _first_not_none(
            getattr(crop, "heat_tolerance_days", None),
            getattr(crop, "heat_tolerance", None),
        )
    )

    if _has_explicit_requirements(
        optimal_temp_min_c=optimal_temp_min_c,
        optimal_temp_max_c=optimal_temp_max_c,
        tolerable_temp_min_c=tolerable_temp_min_c,
        tolerable_temp_max_c=tolerable_temp_max_c,
        preferred_rainfall_min_mm=preferred_rainfall_min_mm,
        preferred_rainfall_max_mm=preferred_rainfall_max_mm,
        frost_tolerance_days=frost_tolerance_days,
        heat_tolerance_days=heat_tolerance_days,
    ):
        rainfall_requirement_mm = _coerce_float(getattr(crop, "rainfall_requirement_mm", None))
        if preferred_rainfall_min_mm is None or preferred_rainfall_max_mm is None:
            preferred_rainfall_min_mm, preferred_rainfall_max_mm = _derive_rainfall_band(
                rainfall_requirement_mm,
                crop,
            )
        tolerable_temp_min_c, tolerable_temp_max_c = _derive_tolerable_temperature_band(
            optimal_temp_min_c,
            optimal_temp_max_c,
            tolerable_temp_min_c,
            tolerable_temp_max_c,
        )
        return CropClimateRequirements(
            optimal_temp_min_c=optimal_temp_min_c,
            optimal_temp_max_c=optimal_temp_max_c,
            tolerable_temp_min_c=tolerable_temp_min_c,
            tolerable_temp_max_c=tolerable_temp_max_c,
            preferred_rainfall_min_mm=preferred_rainfall_min_mm,
            preferred_rainfall_max_mm=preferred_rainfall_max_mm,
            frost_tolerance_days=frost_tolerance_days,
            heat_tolerance_days=heat_tolerance_days,
            source="explicit",
        )

    crop_name = str(getattr(crop, "crop_name", "") or "").strip().casefold()
    if crop_name in _NAMED_CROP_DEFAULTS:
        defaults = _NAMED_CROP_DEFAULTS[crop_name]
        return defaults

    rainfall_min, rainfall_max = _derive_rainfall_band(
        _coerce_float(getattr(crop, "rainfall_requirement_mm", None)),
        crop,
    )
    optimal_temp_min_c, optimal_temp_max_c = _derive_temperature_band_from_sensitivity(crop)
    tolerable_temp_min_c, tolerable_temp_max_c = _derive_tolerable_temperature_band(
        optimal_temp_min_c,
        optimal_temp_max_c,
        None,
        None,
    )

    return CropClimateRequirements(
        optimal_temp_min_c=optimal_temp_min_c,
        optimal_temp_max_c=optimal_temp_max_c,
        tolerable_temp_min_c=tolerable_temp_min_c,
        tolerable_temp_max_c=tolerable_temp_max_c,
        preferred_rainfall_min_mm=rainfall_min,
        preferred_rainfall_max_mm=rainfall_max,
        frost_tolerance_days=_tolerance_from_sensitivity(getattr(crop, "frost_sensitivity", None)),
        heat_tolerance_days=_heat_tolerance_from_sensitivity(getattr(crop, "heat_sensitivity", None)),
        source="heuristic",
    )


def _has_explicit_requirements(**values: object) -> bool:
    return any(value is not None for value in values.values())


def _first_not_none(*values: object) -> object | None:
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_enum_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _derive_rainfall_band(
    rainfall_requirement_mm: float | None,
    crop: Any,
) -> tuple[float | None, float | None]:
    if rainfall_requirement_mm is not None and rainfall_requirement_mm > 0:
        return (
            round(rainfall_requirement_mm * 0.85, 2),
            round(rainfall_requirement_mm * 1.15, 2),
        )

    water_requirement_level = (_normalize_enum_value(getattr(crop, "water_requirement_level", None)) or "medium").lower()
    return _WATER_REQUIREMENT_RAINFALL_DEFAULTS.get(
        water_requirement_level,
        _WATER_REQUIREMENT_RAINFALL_DEFAULTS["medium"],
    )


def _derive_temperature_band_from_sensitivity(crop: Any) -> tuple[float, float]:
    water_requirement_level = (_normalize_enum_value(getattr(crop, "water_requirement_level", None)) or "medium").lower()
    heat_sensitivity = (_normalize_enum_value(getattr(crop, "heat_sensitivity", None)) or "medium").lower()
    if water_requirement_level == "low":
        band = (16.0, 30.0)
    elif water_requirement_level == "high":
        band = (18.0, 29.0)
    else:
        band = (15.0, 27.0)

    if heat_sensitivity == "high":
        return (band[0] - 1.0, band[1] - 2.0)
    if heat_sensitivity == "low":
        return (band[0] + 1.0, band[1] + 2.0)
    return band


def _derive_tolerable_temperature_band(
    optimal_temp_min_c: float | None,
    optimal_temp_max_c: float | None,
    tolerable_temp_min_c: float | None,
    tolerable_temp_max_c: float | None,
) -> tuple[float | None, float | None]:
    if optimal_temp_min_c is None or optimal_temp_max_c is None:
        return tolerable_temp_min_c, tolerable_temp_max_c

    return (
        tolerable_temp_min_c if tolerable_temp_min_c is not None else round(optimal_temp_min_c - 5.0, 2),
        tolerable_temp_max_c if tolerable_temp_max_c is not None else round(optimal_temp_max_c + 5.0, 2),
    )


def _tolerance_from_sensitivity(value: Any) -> int:
    normalized = (_normalize_enum_value(value) or "medium").lower()
    return _SENSITIVITY_TOLERANCE_DEFAULTS.get(normalized, _SENSITIVITY_TOLERANCE_DEFAULTS["medium"])


def _heat_tolerance_from_sensitivity(value: Any) -> int:
    normalized = (_normalize_enum_value(value) or "medium").lower()
    if normalized == "high":
        return 4
    if normalized == "low":
        return 12
    return 8
