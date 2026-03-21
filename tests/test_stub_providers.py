from app.ai.contracts.explanation import (
    RankedExplanationRequest,
    SuitabilityExplanationRequest,
    adapt_explanation_output,
    build_explanation_input_from_ranked_request,
    build_explanation_input_from_suitability_request,
)
from app.ai.contracts.extraction import ExtractionInput, ExtractionRequest
from app.ai.contracts.risk import RiskScoringRequest
from app.ai.contracts.yield_prediction import build_yield_prediction_input_from_entities
from app.ai.providers.stub.explanation import DeterministicExplanationProvider
from app.ai.providers.stub.extraction import StubExtractionProvider
from app.ai.providers.stub.risk import StubRiskScorer
from app.ai.providers.stub.yield_prediction import DeterministicYieldPredictor, StubYieldPredictor
from app.engines.scoring_types import ScoreBlocker, ScoreComponent, ScorePenalty, ScoreStatus
from app.engines.suitability_engine import calculate_suitability
from app.models.crop_price import CropPrice
from app.models.crop_profile import CropProfile
from app.models.enums import CropDrainageRequirement, CropPreferenceLevel, CropSensitivityLevel, WaterRequirementLevel
from app.models.field import Field
from app.models.input_cost import InputCost
from app.models.soil_test import SoilTest
from app.schemas.weather_history import ClimateSummary


def _build_field() -> Field:
    return Field(
        name="Stub Field",
        location_name="Konya",
        latitude=37.8715,
        longitude=32.4846,
        area_hectares=18.0,
        slope_percent=3.0,
        irrigation_available=True,
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
        crop_price=CropPrice(price_per_ton=210.0),
        input_cost=InputCost(fertilizer_cost=240.0, water_cost=165.0, labor_cost=130.0),
    )


def _build_soil() -> SoilTest:
    return SoilTest(
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


def _build_climate() -> ClimateSummary:
    return ClimateSummary(
        avg_temp=23.0,
        total_rainfall=620.0,
        frost_days=1,
        heat_days=3,
    )


def test_stub_yield_predictor_returns_deterministic_request_result():
    provider = DeterministicYieldPredictor()
    field = _build_field()
    field.id = 12
    crop = _build_crop()
    crop.id = 4
    request = build_yield_prediction_input_from_entities(
        field,
        crop,
        soil_test=_build_soil(),
        climate_summary=_build_climate(),
    )

    first = provider.predict(request)
    second = provider.predict(request)

    assert first.predicted_yield == 8.5
    assert first.yield_range_min == 7.62
    assert first.yield_range_max == 9.38
    assert first.confidence == 0.78
    assert first.provider_name == "deterministic_stub_provider"
    assert first.provider_version == "v1"
    assert first.generated_at.tzinfo is not None
    assert second.predicted_yield == first.predicted_yield
    assert second.yield_range_min == first.yield_range_min
    assert second.yield_range_max == first.yield_range_max
    assert second.confidence == first.confidence
    assert second.provider_name == first.provider_name
    assert second.provider_version == first.provider_version


def test_stub_yield_predictor_predicts_from_input_without_db():
    provider = StubYieldPredictor()
    field = _build_field()
    crop = _build_crop()
    soil = _build_soil()
    climate = _build_climate()
    request = build_yield_prediction_input_from_entities(
        field,
        crop,
        soil_test=soil,
        climate_summary=climate,
    )

    first = provider.predict(request)
    second = provider.predict(request)

    assert first.predicted_yield == 8.5
    assert first.provider_name == "deterministic_stub_provider"
    assert first.provider_version == "v1"
    assert second.predicted_yield == first.predicted_yield


def test_deterministic_explanation_provider_returns_non_empty_structured_output():
    field = _build_field()
    crop = _build_crop()
    soil = _build_soil()
    result = calculate_suitability(field, crop, soil)
    provider = DeterministicExplanationProvider()

    output = provider.explain(
        build_explanation_input_from_suitability_request(
            SuitabilityExplanationRequest(
                result=result,
                field_obj=field,
                crop=crop,
            )
        )
    )
    explanation = adapt_explanation_output(output)

    assert explanation.short_explanation.startswith("Stub explanation:")
    assert "DeterministicExplanationProvider" in explanation.detailed_explanation
    assert explanation.strengths
    assert explanation.weaknesses
    assert explanation.risks
    assert output.provider_name == "deterministic_stub_provider"
    assert output.provider_version == "v1"
    assert output.confidence_note
    assert output.generated_at.tzinfo is not None


def test_stub_risk_scorer_orders_blockers_before_component_messages():
    provider = StubRiskScorer()
    request = RiskScoringRequest(
        blockers=[
            ScoreBlocker(code="blocked", dimension="climate", message="High frost risk detected."),
        ],
        breakdown={
            "soil_compatibility": ScoreComponent(
                key="soil_compatibility",
                label="Soil",
                weight=1.0,
                awarded_points=0.0,
                max_points=20.0,
                status=ScoreStatus.MISSING,
                reasons=["Soil texture data missing."],
            ),
            "water_availability_compatibility": ScoreComponent(
                key="water_availability_compatibility",
                label="Water availability",
                weight=1.0,
                awarded_points=4.0,
                max_points=15.0,
                status=ScoreStatus.LIMITED,
                reasons=["Water access is limited during peak demand."],
            ),
        },
    )

    assessment = provider.score(request)

    assert assessment.risks == [
        "High frost risk detected. (stub provider)",
        "Soil texture data missing. (stub provider)",
        "Water access is limited during peak demand. (stub provider)",
    ]


def test_stub_extraction_provider_uses_priority_order():
    provider = StubExtractionProvider()
    payload = {
        "normalized_text": "  Already normalized output  ",
        "text": "Ignored",
        "message": "Ignored",
        "output": [
            {
                "content": [
                    {
                        "text": "Ignored",
                    }
                ]
            }
        ],
    }

    result = provider.extract(ExtractionRequest(payload=payload))

    assert result.text == "Stub extraction result: Already normalized output"


def test_stub_extraction_provider_falls_back_to_stable_payload_summary():
    provider = StubExtractionProvider()

    result = provider.extract(ExtractionRequest(payload={"beta": 2, "alpha": 1}))

    assert result.text == 'Stub extraction result: {"keys": ["alpha", "beta"]}'


def test_stub_extraction_provider_returns_structured_mock_outputs_by_kind():
    provider = StubExtractionProvider()

    fertilizer = provider.extract(
        ExtractionInput(
            raw_text="Apply NPK fertilizer before planting.",
            source_url="https://example.com/fertilizer",
            source_type="webpage",
            extraction_kind="fertilizer",
        )
    )
    crop_requirements = provider.extract(
        ExtractionInput(
            raw_text="Corn prefers moderate drainage and high water.",
            source_url="https://example.com/crop",
            source_type="manual",
            extraction_kind="crop_requirements",
        )
    )
    irrigation = provider.extract(
        ExtractionInput(
            raw_text="Use drip irrigation weekly during vegetative growth.",
            source_url="https://example.com/irrigation",
            source_type="webpage",
            extraction_kind="irrigation",
        )
    )

    assert fertilizer.normalized_json["fertilizer_name"] == "NPK 20-20-20"
    assert fertilizer.missing_fields == ["application_window"]
    assert fertilizer.provider_name == "deterministic_stub_provider"
    assert crop_requirements.normalized_json["crop_name"] == "Corn"
    assert crop_requirements.missing_fields == ["heat_tolerance_days"]
    assert irrigation.normalized_json["irrigation_method"] == "drip"
    assert irrigation.missing_fields == ["distribution_uniformity"]


def test_deterministic_explanation_provider_handles_ranked_requests():
    field = _build_field()
    crop = _build_crop()
    soil = _build_soil()
    result = calculate_suitability(field, crop, soil)
    provider = DeterministicExplanationProvider()

    output = provider.explain(
        build_explanation_input_from_ranked_request(
            RankedExplanationRequest(
                field_name=field.name,
                total_score=result.total_score,
                ranking_score=result.total_score,
                breakdown=result.score_breakdown,
                blockers=result.blockers,
                reasons=result.reasons,
                penalties=[ScorePenalty(dimension=penalty.dimension, points_lost=penalty.points_lost, message=penalty.message) for penalty in result.penalties],
                economic_strengths=[],
                economic_weaknesses=[],
            )
        )
    )
    explanation = adapt_explanation_output(output)

    assert explanation.short_explanation.startswith("Stub explanation:")
    assert explanation.risks
    assert output.provider_name == "deterministic_stub_provider"
