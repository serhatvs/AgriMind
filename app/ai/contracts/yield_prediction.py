"""Contracts and compatibility helpers for yield-prediction providers.

Example:
```python
from app.ai.contracts.yield_prediction import (
    YieldClimateSummary,
    YieldCropSummary,
    YieldFieldSummary,
    YieldPredictionInput,
    YieldSoilSummary,
    adapt_yield_prediction_output,
)
from app.ai.providers.stub.yield_prediction import DeterministicYieldPredictor

input_data = YieldPredictionInput(
    field=YieldFieldSummary(
        field_id=101,
        name="North Parcel",
        area_hectares=18.0,
        slope_percent=3.2,
        irrigation_available=True,
        drainage_quality="good",
        elevation_meters=1020.0,
        infrastructure_score=78,
        water_source_type="well",
        aspect="south",
    ),
    soil=YieldSoilSummary(
        soil_test_id=8,
        ph=6.4,
        ec=0.9,
        organic_matter_percent=3.7,
        nitrogen_ppm=68.0,
        phosphorus_ppm=29.0,
        potassium_ppm=235.0,
        depth_cm=145.0,
        water_holding_capacity=24.0,
        texture_class="loamy",
        drainage_class="good",
        sample_date=None,
    ),
    crop=YieldCropSummary(
        crop_id=7,
        crop_name="Corn",
        water_requirement_level="high",
        drainage_requirement="moderate",
        salinity_tolerance="moderate",
        rooting_depth_cm=150.0,
        slope_tolerance=8.0,
        optimal_temp_min_c=18.0,
        optimal_temp_max_c=30.0,
        rainfall_requirement_mm=550.0,
        frost_tolerance_days=4,
        heat_tolerance_days=18,
        organic_matter_preference="moderate",
    ),
    climate=YieldClimateSummary(
        avg_temp=23.0,
        total_rainfall=620.0,
        frost_days=1,
        heat_days=3,
    ),
)

provider = DeterministicYieldPredictor()
output = provider.predict(input_data)
legacy_result = adapt_yield_prediction_output(input_data, output)
```
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from app.ai.contracts.metadata import AITraceMetadata
from app.models.crop_profile import CropProfile
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.schemas.ai_metadata import AITraceMetadataRead
from app.schemas.weather_history import ClimateSummary
from app.schemas.yield_prediction import YieldPredictionRange, YieldPredictionResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass(slots=True)
class YieldFieldSummary:
    """Normalized field attributes used by yield prediction providers."""

    field_id: int | None
    name: str
    area_hectares: float
    slope_percent: float
    irrigation_available: bool
    drainage_quality: str
    elevation_meters: float | None
    infrastructure_score: int | None
    water_source_type: str | None
    aspect: str | None


@dataclass(slots=True)
class YieldSoilSummary:
    """Normalized latest-soil attributes used by yield prediction providers."""

    soil_test_id: int | None
    ph: float | None
    ec: float | None
    organic_matter_percent: float | None
    nitrogen_ppm: float | None
    phosphorus_ppm: float | None
    potassium_ppm: float | None
    depth_cm: float | None
    water_holding_capacity: float | None
    texture_class: str | None
    drainage_class: str | None
    sample_date: datetime | None


@dataclass(slots=True)
class YieldCropSummary:
    """Normalized crop requirements used by yield prediction providers."""

    crop_id: int | None
    crop_name: str
    water_requirement_level: str
    drainage_requirement: str
    salinity_tolerance: str | None
    rooting_depth_cm: float | None
    slope_tolerance: float | None
    optimal_temp_min_c: float | None
    optimal_temp_max_c: float | None
    rainfall_requirement_mm: float | None
    frost_tolerance_days: int | None
    heat_tolerance_days: int | None
    organic_matter_preference: str | None


@dataclass(slots=True)
class YieldClimateSummary:
    """Normalized climate aggregates used by yield prediction providers."""

    avg_temp: float | None
    total_rainfall: float | None
    frost_days: int | None
    heat_days: int | None


@dataclass(slots=True)
class YieldPredictionInput:
    """Canonical provider input for yield prediction."""

    field: YieldFieldSummary
    soil: YieldSoilSummary | None
    crop: YieldCropSummary
    climate: YieldClimateSummary | None


@dataclass(slots=True)
class YieldPredictionOutput:
    """Canonical provider output for yield prediction."""

    predicted_yield: float
    yield_range_min: float
    yield_range_max: float
    metadata: AITraceMetadata

    @property
    def confidence(self) -> float | None:
        return self.metadata.confidence

    @property
    def provider_name(self) -> str:
        return self.metadata.provider_name

    @property
    def provider_version(self) -> str | None:
        return self.metadata.provider_version

    @property
    def generated_at(self) -> datetime:
        return self.metadata.generated_at

    @property
    def debug_info(self) -> dict[str, object] | None:
        return self.metadata.debug_info


@dataclass(slots=True)
class YieldPredictionRequest:
    """Compatibility request identifying a persisted field/crop pairing."""

    field_id: int
    crop_id: int


@dataclass(slots=True)
class YieldPredictionContext:
    """Compatibility request providing assembled ORM entities."""

    field_obj: Field
    crop: CropProfile
    soil_test: SoilTest | None = None
    climate_summary: ClimateSummary | None = None


class YieldPredictor(Protocol):
    """Predict yield from a transport-friendly summary input."""

    def predict(self, request: YieldPredictionInput) -> YieldPredictionOutput:
        """Return a canonical yield prediction for `request`."""

    @property
    def model_dir(self) -> Path:
        """Return the provider's artifact directory."""


@runtime_checkable
class YieldPredictionServiceClient(Protocol):
    """Compatibility client used by business services during migration."""

    def predict_from_context(self, request: YieldPredictionContext) -> YieldPredictionResult:
        """Return the legacy yield result shape for an assembled ORM context."""


def build_yield_prediction_input_from_entities(
    field_obj: Field,
    crop: CropProfile,
    soil_test: SoilTest | None = None,
    climate_summary: ClimateSummary | None = None,
) -> YieldPredictionInput:
    """Build the canonical provider input from ORM entities."""

    from app.ai.features.loaders import build_feature_summary_bundle
    from app.ai.features.yield_prediction import build_yield_prediction_input_from_summary

    summary = build_feature_summary_bundle(
        field_obj,
        crop,
        soil_test=soil_test,
        climate_summary=climate_summary,
    )
    return build_yield_prediction_input_from_summary(summary)


def build_yield_prediction_input_from_context(request: YieldPredictionContext) -> YieldPredictionInput:
    """Build the canonical provider input from a compatibility context."""

    return build_yield_prediction_input_from_entities(
        request.field_obj,
        request.crop,
        soil_test=request.soil_test,
        climate_summary=request.climate_summary,
    )


def load_yield_prediction_input(
    db: "Session",
    field_id: int,
    crop_id: int,
) -> YieldPredictionInput:
    """Load ORM entities and convert them into the canonical provider input."""

    from app.ai.features.yield_prediction import build_yield_prediction_input

    return build_yield_prediction_input(db, field_id, crop_id)


def adapt_yield_prediction_output(
    input_data: YieldPredictionInput,
    output: YieldPredictionOutput,
) -> YieldPredictionResult:
    """Adapt canonical provider output to the legacy service result shape."""

    feature_snapshot = _feature_snapshot_from_input(input_data)
    feature_snapshot["generated_at"] = _ensure_utc(output.generated_at).isoformat()

    return YieldPredictionResult(
        field_id=input_data.field.field_id or 0,
        crop_id=input_data.crop.crop_id or 0,
        predicted_yield_per_hectare=round(max(output.predicted_yield, 0.0), 2),
        predicted_yield_range=YieldPredictionRange(
            min=round(max(output.yield_range_min, 0.0), 2),
            max=round(max(output.yield_range_max, 0.0), 2),
        ),
        confidence_score=round(min(max(output.confidence or 0.0, 0.0), 1.0), 2),
        model_version=output.provider_version or "unknown",
        training_source=output.provider_name,
        feature_snapshot=feature_snapshot,
        metadata=adapt_trace_metadata(output.metadata),
    )


def _feature_snapshot_from_input(input_data: YieldPredictionInput) -> dict[str, object]:
    soil = input_data.soil
    climate = input_data.climate

    return {
        "crop_name": input_data.crop.crop_name,
        "soil_ph": soil.ph if soil is not None else None,
        "soil_ec": soil.ec if soil is not None else None,
        "organic_matter_percent": soil.organic_matter_percent if soil is not None else None,
        "nitrogen_ppm": soil.nitrogen_ppm if soil is not None else None,
        "phosphorus_ppm": soil.phosphorus_ppm if soil is not None else None,
        "potassium_ppm": soil.potassium_ppm if soil is not None else None,
        "soil_depth_cm": soil.depth_cm if soil is not None else None,
        "water_holding_capacity": soil.water_holding_capacity if soil is not None else None,
        "texture_class": soil.texture_class if soil is not None else None,
        "soil_drainage_class": soil.drainage_class if soil is not None else None,
        "slope_percent": input_data.field.slope_percent,
        "irrigation_available": input_data.field.irrigation_available,
        "area_hectares": input_data.field.area_hectares,
        "elevation_meters": input_data.field.elevation_meters,
        "field_drainage_quality": input_data.field.drainage_quality,
        "infrastructure_score": input_data.field.infrastructure_score,
        "water_source_type": input_data.field.water_source_type,
        "aspect": input_data.field.aspect,
        "crop_water_requirement": input_data.crop.water_requirement_level,
        "crop_drainage_requirement": input_data.crop.drainage_requirement,
        "crop_salinity_tolerance": input_data.crop.salinity_tolerance,
        "crop_rooting_depth_cm": input_data.crop.rooting_depth_cm,
        "crop_slope_tolerance": input_data.crop.slope_tolerance,
        "crop_optimal_temp_min_c": input_data.crop.optimal_temp_min_c,
        "crop_optimal_temp_max_c": input_data.crop.optimal_temp_max_c,
        "crop_rainfall_requirement_mm": input_data.crop.rainfall_requirement_mm,
        "crop_frost_tolerance_days": input_data.crop.frost_tolerance_days,
        "crop_heat_tolerance_days": input_data.crop.heat_tolerance_days,
        "crop_organic_matter_preference": input_data.crop.organic_matter_preference,
        "climate_avg_temp": climate.avg_temp if climate is not None else None,
        "climate_total_rainfall": climate.total_rainfall if climate is not None else None,
        "climate_frost_days": climate.frost_days if climate is not None else None,
        "climate_heat_days": climate.heat_days if climate is not None else None,
        "has_soil_test": soil is not None,
        "has_climate_summary": climate is not None,
    }


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def adapt_trace_metadata(metadata: AITraceMetadata) -> AITraceMetadataRead:
    """Adapt reusable contract metadata into the API-safe metadata schema."""

    normalized = metadata.normalized()
    return AITraceMetadataRead(
        provider_name=normalized.provider_name,
        provider_version=normalized.provider_version,
        generated_at=normalized.generated_at,
        confidence=normalized.confidence,
        debug_info=normalized.debug_info,
    )

YieldPredictionProvider = YieldPredictor
