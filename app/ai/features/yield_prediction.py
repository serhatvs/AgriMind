"""Assemble canonical yield-prediction inputs from shared feature summaries.

Example:
```python
from app.ai.features.yield_prediction import build_yield_prediction_input

input_data = build_yield_prediction_input(db, field_id=1, crop_id=2)
print(input_data.field.name)
print(input_data.crop.crop_name)
```
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.contracts.yield_prediction import (
    YieldClimateSummary,
    YieldCropSummary,
    YieldFieldSummary,
    YieldPredictionInput,
    YieldSoilSummary,
)
from app.ai.features.loaders import assemble_feature_bundle
from app.ai.features.types import FeatureSummaryBundle
from app.services.weather_service import WeatherService


def build_yield_prediction_input(
    db: Session,
    field_id: int,
    crop_id: int,
    *,
    weather_service: WeatherService | None = None,
) -> YieldPredictionInput:
    """Load persisted data and map it into the canonical yield provider input."""

    bundle = assemble_feature_bundle(
        db,
        field_id,
        crop_id,
        weather_service=weather_service,
    )
    return build_yield_prediction_input_from_summary(bundle.summary)


def build_yield_prediction_input_from_summary(
    summary: FeatureSummaryBundle,
) -> YieldPredictionInput:
    """Map shared feature summaries into the yield provider contract."""

    return YieldPredictionInput(
        field=YieldFieldSummary(
            field_id=summary.field.field_id,
            name=summary.field.name,
            area_hectares=_float_or_default(summary.field.area_hectares),
            slope_percent=_float_or_default(summary.field.slope_percent),
            irrigation_available=_bool_or_default(summary.field.irrigation_available),
            drainage_quality=summary.field.drainage_quality or "",
            elevation_meters=summary.field.elevation_meters,
            infrastructure_score=summary.field.infrastructure_score,
            water_source_type=summary.field.water_source_type,
            aspect=summary.field.aspect,
        ),
        soil=(
            YieldSoilSummary(
                soil_test_id=summary.soil.soil_test_id,
                ph=summary.soil.ph,
                ec=summary.soil.ec,
                organic_matter_percent=summary.soil.organic_matter_percent,
                nitrogen_ppm=summary.soil.nitrogen_ppm,
                phosphorus_ppm=summary.soil.phosphorus_ppm,
                potassium_ppm=summary.soil.potassium_ppm,
                calcium_ppm=summary.soil.calcium_ppm,
                magnesium_ppm=summary.soil.magnesium_ppm,
                depth_cm=summary.soil.depth_cm,
                water_holding_capacity=summary.soil.water_holding_capacity,
                texture_class=summary.soil.texture_class,
                drainage_class=summary.soil.drainage_class,
                sample_date=summary.soil.sample_date,
            )
            if summary.soil is not None
            else None
        ),
        crop=YieldCropSummary(
            crop_id=summary.crop.crop_id,
            crop_name=summary.crop.crop_name,
            ideal_ph_min=summary.crop.ideal_ph_min,
            ideal_ph_max=summary.crop.ideal_ph_max,
            water_requirement_level=summary.crop.water_requirement_level or "",
            drainage_requirement=summary.crop.drainage_requirement or "",
            frost_sensitivity=summary.crop.frost_sensitivity,
            heat_sensitivity=summary.crop.heat_sensitivity,
            salinity_tolerance=summary.crop.salinity_tolerance,
            rooting_depth_cm=summary.crop.rooting_depth_cm,
            slope_tolerance=summary.crop.slope_tolerance,
            optimal_temp_min_c=summary.crop.optimal_temp_min_c,
            optimal_temp_max_c=summary.crop.optimal_temp_max_c,
            rainfall_requirement_mm=summary.crop.rainfall_requirement_mm,
            frost_tolerance_days=summary.crop.frost_tolerance_days,
            heat_tolerance_days=summary.crop.heat_tolerance_days,
            organic_matter_preference=summary.crop.organic_matter_preference,
        ),
        climate=(
            YieldClimateSummary(
                avg_temp=summary.climate.avg_temp,
                min_observed_temp=summary.climate.min_observed_temp,
                max_observed_temp=summary.climate.max_observed_temp,
                total_rainfall=summary.climate.total_rainfall,
                frost_days=summary.climate.frost_days,
                heat_days=summary.climate.heat_days,
                avg_humidity=summary.climate.avg_humidity,
                avg_wind_speed=summary.climate.avg_wind_speed,
                avg_solar_radiation=summary.climate.avg_solar_radiation,
                weather_record_count=summary.climate.weather_record_count,
            )
            if summary.climate is not None
            else None
        ),
    )


def _float_or_default(value: float | None, default: float = 0.0) -> float:
    return value if value is not None else default


def _bool_or_default(value: bool | None, default: bool = False) -> bool:
    return value if value is not None else default
