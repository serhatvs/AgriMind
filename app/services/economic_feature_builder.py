"""Build reusable profitability features from field, crop, yield, and climate inputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas.weather_history import ClimateSummary
from app.schemas.yield_prediction import YieldPredictionResult


@dataclass(frozen=True, slots=True)
class EconomicFieldFeatures:
    """Normalized field context used for economic scoring."""

    irrigation_available: bool
    infrastructure_score: int | None
    area_hectares: float
    location_name: str | None = None


@dataclass(frozen=True, slots=True)
class EconomicCropFeatures:
    """Normalized crop context used for economic scoring."""

    crop_name: str
    water_requirement_level: str | None
    rooting_depth_cm: float | None


@dataclass(frozen=True, slots=True)
class EconomicClimateStressFeatures:
    """Optional stress indicators that can increase production risk costs."""

    frost_days: int = 0
    heat_days: int = 0
    weather_record_count: int = 0


@dataclass(frozen=True, slots=True)
class CropEconomicProfileSnapshot:
    """Normalized crop economics configuration used during profit estimation."""

    crop_name: str
    average_market_price_per_unit: float
    price_unit: str
    base_cost_per_hectare: float
    irrigation_cost_factor: float
    fertilizer_cost_factor: float
    labor_cost_factor: float
    risk_cost_factor: float
    region: str | None = None
    source_name: str = "static"


@dataclass(frozen=True, slots=True)
class EconomicFeatureInput:
    """Canonical profitability feature bundle independent from ORM objects."""

    predicted_yield: float | None
    predicted_yield_confidence: float | None
    field: EconomicFieldFeatures
    crop: EconomicCropFeatures
    climate_stress: EconomicClimateStressFeatures | None
    economic_profile: CropEconomicProfileSnapshot | None


class EconomicFeatureBuilder:
    """Build profitability feature bundles from assembled entities."""

    def build_from_entities(
        self,
        field_obj: Any,
        crop: Any,
        *,
        yield_prediction: YieldPredictionResult | None,
        climate_summary: ClimateSummary | None,
        economic_profile: CropEconomicProfileSnapshot | None,
    ) -> EconomicFeatureInput:
        """Normalize persisted entities into profitability features."""

        return EconomicFeatureInput(
            predicted_yield=(
                float(yield_prediction.predicted_yield_per_hectare)
                if yield_prediction is not None
                else None
            ),
            predicted_yield_confidence=(
                float(yield_prediction.confidence_score)
                if yield_prediction is not None and yield_prediction.confidence_score is not None
                else None
            ),
            field=EconomicFieldFeatures(
                irrigation_available=bool(getattr(field_obj, "irrigation_available", False)),
                infrastructure_score=_coerce_optional_int(getattr(field_obj, "infrastructure_score", None)),
                area_hectares=_coerce_float(getattr(field_obj, "area_hectares", None), default=0.0),
                location_name=getattr(field_obj, "location_name", None),
            ),
            crop=EconomicCropFeatures(
                crop_name=str(getattr(crop, "crop_name", "")),
                water_requirement_level=_enum_value(getattr(crop, "water_requirement_level", None)),
                rooting_depth_cm=_coerce_optional_float(getattr(crop, "rooting_depth_cm", None)),
            ),
            climate_stress=(
                EconomicClimateStressFeatures(
                    frost_days=int(climate_summary.frost_days or 0),
                    heat_days=int(climate_summary.heat_days or 0),
                    weather_record_count=int(climate_summary.weather_record_count or 0),
                )
                if climate_summary is not None
                else None
            ),
            economic_profile=economic_profile,
        )


def _coerce_float(value: Any, *, default: float) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_optional_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", value)
