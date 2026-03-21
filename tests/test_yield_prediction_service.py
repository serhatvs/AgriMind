from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.ai.contracts.metadata import AITraceMetadata
from app.ai.contracts.yield_prediction import (
    YieldClimateSummary,
    YieldCropSummary,
    YieldFieldSummary,
    YieldPredictionInput,
    YieldPredictionOutput,
)

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


def _sample_prediction_input() -> YieldPredictionInput:
    return YieldPredictionInput(
        field=YieldFieldSummary(
            field_id=101,
            name="Registry Field",
            area_hectares=12.5,
            slope_percent=2.1,
            irrigation_available=True,
            drainage_quality="good",
            elevation_meters=900.0,
            infrastructure_score=75,
            water_source_type="well",
            aspect="south",
        ),
        soil=None,
        crop=YieldCropSummary(
            crop_id=7,
            crop_name="Corn",
            water_requirement_level="high",
            drainage_requirement="moderate",
            salinity_tolerance="moderate",
            rooting_depth_cm=120.0,
            slope_tolerance=8.0,
            optimal_temp_min_c=18.0,
            optimal_temp_max_c=30.0,
            rainfall_requirement_mm=550.0,
            frost_tolerance_days=4,
            heat_tolerance_days=18,
            organic_matter_preference="moderate",
        ),
        climate=YieldClimateSummary(
            avg_temp=22.0,
            total_rainfall=610.0,
            frost_days=1,
            heat_days=3,
        ),
    )


class _RegistryYieldProvider:
    def __init__(self) -> None:
        self._model_dir = Path("registry-model")
        self.requests: list[YieldPredictionInput] = []

    @property
    def model_dir(self) -> Path:
        return self._model_dir

    def predict(self, request: YieldPredictionInput) -> YieldPredictionOutput:
        self.requests.append(request)
        return YieldPredictionOutput(
            predicted_yield=7.8,
            yield_range_min=7.0,
            yield_range_max=8.6,
            metadata=AITraceMetadata(
                provider_name="registry-test",
                provider_version="v1",
                generated_at=datetime.now(timezone.utc),
                confidence=0.74,
            ),
        )


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


def test_yield_prediction_service_uses_registry_provider_by_default(monkeypatch, tmp_path):
    class _RecordingRegistry:
        def __init__(self, provider: _RegistryYieldProvider) -> None:
            self.provider = provider
            self.calls: list[dict[str, object]] = []

        def get_yield_prediction_provider(self, *, db, model_dir=None):
            self.calls.append({"db": db, "model_dir": model_dir})
            return self.provider

    provider = _RegistryYieldProvider()
    registry = _RecordingRegistry(provider)
    monkeypatch.setattr(
        "app.ai.orchestration.yield_prediction.get_ai_provider_registry",
        lambda: registry,
    )

    service = YieldPredictionService(None, model_dir=tmp_path / "yield_model")
    output = service.predict(_sample_prediction_input())

    assert service.provider is provider
    assert registry.calls == [{"db": None, "model_dir": tmp_path / "yield_model"}]
    assert len(provider.requests) == 1
    assert output.provider_name == "registry-test"


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
