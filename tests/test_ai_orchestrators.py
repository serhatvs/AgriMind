from datetime import date, datetime, timedelta, timezone

import httpx

from app.ai.contracts.metadata import AITraceMetadata
from app.ai.contracts.extraction import ExtractionResult
from app.ai.orchestration.recommendation import RecommendationOrchestrator
from app.ai.orchestration.yield_prediction import YieldPredictionOrchestrator
from app.ai.providers.llm.openai_responses import OpenAIResponsesClient
from app.ai.providers.stub.explanation import DeterministicExplanationProvider
from app.ai.providers.stub.extraction import StubExtractionProvider
from app.ai.providers.stub.yield_prediction import StubYieldPredictor
from app.engines.explanation_engine import generate_explanation
from app.engines.suitability_engine import calculate_suitability
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


class _RecordingExtractionProvider:
    def __init__(self) -> None:
        self.calls = 0

    def extract(self, request):
        self.calls += 1
        assert request.payload["model"] == "gpt-test-version"
        return ExtractionResult(
            normalized_json={"text": "Extracted by provider."},
            metadata=AITraceMetadata(
                provider_name="test-extraction",
                provider_version="v1",
                generated_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
                confidence=0.9,
                debug_info={"source": "recording-test"},
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


def test_recommendation_orchestrator_preserves_legacy_explanation_output():
    field = Field(
        name="North Parcel",
        location_name="North",
        latitude=39.0,
        longitude=-94.0,
        area_hectares=10.0,
        slope_percent=3.0,
        irrigation_available=True,
        drainage_quality="good",
    )
    crop = CropProfile(
        crop_name="Wheat",
        scientific_name="Triticum aestivum",
        ideal_ph_min=6.0,
        ideal_ph_max=7.0,
        tolerable_ph_min=5.5,
        tolerable_ph_max=7.5,
        water_requirement_level=WaterRequirementLevel.MEDIUM,
        drainage_requirement=CropDrainageRequirement.GOOD,
        frost_sensitivity=CropSensitivityLevel.MEDIUM,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        salinity_tolerance=CropPreferenceLevel.MODERATE,
        rooting_depth_cm=120.0,
        slope_tolerance=10.0,
        organic_matter_preference=CropPreferenceLevel.MODERATE,
    )
    soil = SoilTest(
        field_id=1,
        ph=6.5,
        organic_matter_percent=4.0,
        nitrogen_ppm=40.0,
        phosphorus_ppm=25.0,
        potassium_ppm=180.0,
        depth_cm=120.0,
        ec=1.2,
    )

    legacy_result = calculate_suitability(field, crop, soil)
    legacy_explanation = generate_explanation(legacy_result, field, crop)
    orchestrated = RecommendationOrchestrator().generate(field, crop, soil)

    assert orchestrated.suitability.total_score == legacy_result.total_score
    assert orchestrated.explanation.detailed_explanation == legacy_explanation


def test_openai_responses_client_uses_extraction_provider():
    extraction_provider = _RecordingExtractionProvider()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "gpt-test-version", "output": []})

    client = OpenAIResponsesClient(
        api_key="test-key",
        model="gpt-test",
        base_url="https://api.openai.com/v1",
        timeout_seconds=5.0,
        extraction_provider=extraction_provider,
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.openai.com/v1"),
    )

    answer = client.generate_answer(system_prompt="system", user_prompt="user")

    assert answer.text == "Extracted by provider."
    assert extraction_provider.calls == 1


def test_yield_prediction_orchestrator_preserves_result_shape(db, tmp_path):
    field = _build_field()
    crop = _build_crop()
    db.add_all([field, crop])
    db.flush()

    db.add(
        SoilTest(
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
    )

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

    prediction = YieldPredictionOrchestrator(db, model_dir=tmp_path / "yield_model").predict_yield(
        field.id,
        crop.id,
    )

    assert set(prediction.model_dump().keys()) == {
        "field_id",
        "crop_id",
        "predicted_yield_per_hectare",
        "predicted_yield_min",
        "predicted_yield_max",
        "predicted_yield_range",
        "confidence_score",
        "model_version",
        "training_source",
        "feature_snapshot",
        "metadata",
    }


def test_stub_providers_work_through_existing_orchestration_paths():
    field = _build_field()
    crop = _build_crop()
    soil = SoilTest(
        field_id=1,
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

    prediction = YieldPredictionOrchestrator(
        db=None,
        provider=StubYieldPredictor(),
    ).predict_for_entities(field, crop, soil_test=soil)

    recommendation = RecommendationOrchestrator(
        explanation_provider=DeterministicExplanationProvider(),
    ).generate(field, crop, soil)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "gpt-test-version", "text": "placeholder response"})

    answer = OpenAIResponsesClient(
        api_key="test-key",
        model="gpt-test",
        base_url="https://api.openai.com/v1",
        timeout_seconds=5.0,
        extraction_provider=StubExtractionProvider(),
        client_factory=lambda: httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.openai.com/v1"),
    ).generate_answer(system_prompt="system", user_prompt="user")

    assert prediction.model_version == "v1"
    assert prediction.training_source == "deterministic_heuristics"
    assert recommendation.explanation.short_explanation.startswith("Stub explanation:")
    assert answer.text == "Stub extraction result: placeholder response"
