"""Load field-scoped AI inputs and normalize them into shared feature summaries.

Example:
```python
from app.ai.features.loaders import assemble_feature_bundle

bundle = assemble_feature_bundle(db, field_id=1, crop_id=2)
print(bundle.summary.field.name)
print(bundle.summary.soil.ph if bundle.summary.soil is not None else None)
```
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.features.types import (
    ClimateFeatureSummary,
    CropFeatureSummary,
    FeatureAssemblyBundle,
    FeatureSummaryBundle,
    FieldFeatureSummary,
    SoilFeatureSummary,
)
from app.models.crop_profile import CropProfile
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.schemas.weather_history import ClimateSummary
from app.services.crop_service import get_crop
from app.services.errors import NotFoundError
from app.services.field_service import get_field
from app.services.soil_service import get_latest_soil_test_for_field
from app.services.weather_service import WeatherService


def assemble_feature_bundle(
    db: Session,
    field_id: int,
    crop_id: int,
    *,
    weather_service: WeatherService | None = None,
) -> FeatureAssemblyBundle:
    """Load ORM entities once and return raw plus normalized feature summaries."""

    field_obj = get_field(db, field_id)
    if field_obj is None:
        raise NotFoundError(f"Field with id {field_id} not found")

    crop = get_crop(db, crop_id)
    if crop is None:
        raise NotFoundError(f"Crop with id {crop_id} not found")

    soil_test = get_latest_soil_test_for_field(db, field_id)
    weather = weather_service or WeatherService(db)
    climate_summary = weather.get_climate_summary(field_id)

    return FeatureAssemblyBundle(
        field_obj=field_obj,
        crop=crop,
        soil_test=soil_test,
        climate_summary=climate_summary,
        summary=build_feature_summary_bundle(
            field_obj,
            crop,
            soil_test=soil_test,
            climate_summary=climate_summary,
        ),
    )


def build_feature_summary_bundle(
    field_obj: Field,
    crop: CropProfile,
    *,
    soil_test: SoilTest | None = None,
    climate_summary: ClimateSummary | None = None,
) -> FeatureSummaryBundle:
    """Normalize raw entities into transport-friendly AI feature summaries."""

    return FeatureSummaryBundle(
        field=_build_field_summary(field_obj),
        soil=_build_soil_summary(soil_test),
        crop=_build_crop_summary(crop),
        climate=_build_climate_summary(climate_summary),
    )


def _build_field_summary(field_obj: Field) -> FieldFeatureSummary:
    return FieldFeatureSummary(
        field_id=getattr(field_obj, "id", None),
        name=str(getattr(field_obj, "name", "")),
        area_hectares=getattr(field_obj, "area_hectares", None),
        slope_percent=getattr(field_obj, "slope_percent", None),
        irrigation_available=getattr(field_obj, "irrigation_available", None),
        drainage_quality=getattr(field_obj, "drainage_quality", None),
        elevation_meters=getattr(field_obj, "elevation_meters", None),
        infrastructure_score=getattr(field_obj, "infrastructure_score", None),
        water_source_type=_enum_value(getattr(field_obj, "water_source_type", None)),
        aspect=_enum_value(getattr(field_obj, "aspect", None)),
    )


def _build_soil_summary(soil_test: SoilTest | None) -> SoilFeatureSummary | None:
    if soil_test is None:
        return None

    return SoilFeatureSummary(
        soil_test_id=getattr(soil_test, "id", None),
        ph=getattr(soil_test, "ph", None),
        ec=getattr(soil_test, "ec", None),
        organic_matter_percent=getattr(soil_test, "organic_matter_percent", None),
        nitrogen_ppm=getattr(soil_test, "nitrogen_ppm", None),
        phosphorus_ppm=getattr(soil_test, "phosphorus_ppm", None),
        potassium_ppm=getattr(soil_test, "potassium_ppm", None),
        depth_cm=getattr(soil_test, "depth_cm", None),
        water_holding_capacity=getattr(soil_test, "water_holding_capacity", None),
        texture_class=getattr(soil_test, "texture_class", None),
        drainage_class=getattr(soil_test, "drainage_class", None),
        sample_date=getattr(soil_test, "sample_date", None),
    )


def _build_crop_summary(crop: CropProfile) -> CropFeatureSummary:
    return CropFeatureSummary(
        crop_id=getattr(crop, "id", None),
        crop_name=str(getattr(crop, "crop_name", "")),
        water_requirement_level=_enum_value(getattr(crop, "water_requirement_level", None)),
        drainage_requirement=_enum_value(getattr(crop, "drainage_requirement", None)),
        salinity_tolerance=_enum_value(getattr(crop, "salinity_tolerance", None)),
        rooting_depth_cm=getattr(crop, "rooting_depth_cm", None),
        slope_tolerance=getattr(crop, "slope_tolerance", None),
        optimal_temp_min_c=getattr(crop, "optimal_temp_min_c", None),
        optimal_temp_max_c=getattr(crop, "optimal_temp_max_c", None),
        rainfall_requirement_mm=getattr(crop, "rainfall_requirement_mm", None),
        frost_tolerance_days=getattr(crop, "frost_tolerance_days", None),
        heat_tolerance_days=getattr(crop, "heat_tolerance_days", None),
        organic_matter_preference=_enum_value(getattr(crop, "organic_matter_preference", None)),
    )


def _build_climate_summary(climate_summary: ClimateSummary | None) -> ClimateFeatureSummary | None:
    if climate_summary is None:
        return None

    return ClimateFeatureSummary(
        avg_temp=climate_summary.avg_temp,
        total_rainfall=climate_summary.total_rainfall,
        frost_days=climate_summary.frost_days,
        heat_days=climate_summary.heat_days,
    )


def _enum_value(value: object | None) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", value)
