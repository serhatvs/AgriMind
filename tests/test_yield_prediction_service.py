from datetime import date, timedelta

from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    FieldAspect,
    WaterRequirementLevel,
    WaterSourceType,
)
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.models.weather_history import WeatherHistory
from app.services.yield_prediction_service import YieldPredictionService


def _build_field() -> Field:
    return Field(
        name="Yield Test Field",
        location_name="Konya Plain",
        latitude=37.8715,
        longitude=32.4846,
        area_hectares=18.0,
        elevation_meters=1020.0,
        slope_percent=3.2,
        aspect=FieldAspect.SOUTH,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=78,
        drainage_quality="good",
    )


def _build_crop() -> CropProfile:
    return CropProfile(
        crop_name="Corn",
        scientific_name="Zea mays",
        ideal_ph_min=6.0,
        ideal_ph_max=6.8,
        tolerable_ph_min=5.5,
        tolerable_ph_max=7.5,
        water_requirement_level=WaterRequirementLevel.HIGH,
        drainage_requirement=CropDrainageRequirement.MODERATE,
        frost_sensitivity=CropSensitivityLevel.HIGH,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        salinity_tolerance=CropPreferenceLevel.MODERATE,
        rooting_depth_cm=150.0,
        slope_tolerance=8.0,
        optimal_temp_min_c=18.0,
        optimal_temp_max_c=30.0,
        rainfall_requirement_mm=550.0,
        frost_tolerance_days=4,
        heat_tolerance_days=18,
        organic_matter_preference=CropPreferenceLevel.MODERATE,
    )


def test_yield_prediction_service_predicts_for_persisted_entities(db, tmp_path):
    field = _build_field()
    crop = _build_crop()
    db.add_all([field, crop])
    db.flush()

    soil_test = SoilTest(
        field_id=field.id,
        ph=6.4,
        ec=0.9,
        organic_matter_percent=3.7,
        nitrogen_ppm=68.0,
        phosphorus_ppm=29.0,
        potassium_ppm=235.0,
        calcium_ppm=1700.0,
        magnesium_ppm=220.0,
        texture_class="loamy",
        drainage_class="good",
        depth_cm=145.0,
        water_holding_capacity=24.0,
    )
    db.add(soil_test)

    latest_date = date(2026, 3, 15)
    for offset in range(14):
        day = latest_date - timedelta(days=offset)
        db.add(
            WeatherHistory(
                field_id=field.id,
                date=day,
                min_temp=11.0,
                max_temp=27.0,
                avg_temp=19.0,
                rainfall_mm=14.5,
                humidity=56.0,
                wind_speed=3.8,
                solar_radiation=18.0,
                et0=4.6,
            )
        )

    db.commit()

    service = YieldPredictionService(db, model_dir=tmp_path / "yield_model")
    prediction = service.predict_yield(field.id, crop.id)

    assert prediction.field_id == field.id
    assert prediction.crop_id == crop.id
    assert prediction.predicted_yield_per_hectare > 0
    assert prediction.predicted_yield_range.min <= prediction.predicted_yield_per_hectare
    assert prediction.predicted_yield_range.max >= prediction.predicted_yield_per_hectare
    assert prediction.feature_snapshot["has_soil_test"] is True
    assert prediction.feature_snapshot["has_climate_summary"] is True


def test_yield_prediction_service_handles_missing_soil_and_climate(db, tmp_path):
    field = _build_field()
    crop = _build_crop()
    db.add_all([field, crop])
    db.commit()

    service = YieldPredictionService(db, model_dir=tmp_path / "yield_model")
    prediction = service.predict_yield(field.id, crop.id)

    assert prediction.predicted_yield_per_hectare > 0
    assert prediction.feature_snapshot["has_soil_test"] is False
    assert prediction.feature_snapshot["has_climate_summary"] is False
    assert prediction.confidence_score < 1
