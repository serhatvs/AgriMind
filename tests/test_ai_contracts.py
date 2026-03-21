from datetime import datetime, timezone

from app.ai.contracts import (
    AITraceMetadata,
    ExplanationInput,
    ExplanationOutput,
    ExplanationPenalty,
    ExplanationRankingSummary,
    ExplanationScoreComponent,
    ExtractionInput,
    ExtractionOutput,
    ExtractionProvider,
    ExtractionRequest,
    RiskAssessmentInput,
    RiskScorer,
    RiskScoringProvider,
    RiskScoringRequest,
    SuitabilityExplanationRequest,
    TextExtractionProvider,
    YieldClimateSummary,
    YieldCropSummary,
    YieldFieldSummary,
    YieldPredictionInput,
    YieldPredictionOutput,
    YieldPredictionContext,
    YieldPredictionProvider,
    YieldPredictionServiceClient,
    YieldPredictor,
    YieldSoilSummary,
    adapt_explanation_output,
    build_explanation_input_from_suitability_request,
    build_extraction_input_from_payload,
    adapt_yield_prediction_output,
    build_yield_prediction_input_from_entities,
)
from app.ai.orchestration.yield_prediction import YieldPredictionOrchestrator
from app.ai.providers.ml.xgboost_yield import XGBoostYieldPredictionProvider
from app.ai.providers.rule_based.explanation import RuleBasedExplanationProvider
from app.ai.providers.rule_based.extraction import RuleBasedTextExtractionProvider
from app.ai.providers.rule_based.risk import RuleBasedRiskScoringProvider
from app.ai.providers.stub.yield_prediction import StubYieldPredictor
from app.engines.suitability_engine import calculate_suitability
from app.models.crop_price import CropPrice
from app.models.crop_profile import CropProfile
from app.models.enums import CropDrainageRequirement, CropPreferenceLevel, CropSensitivityLevel, WaterRequirementLevel
from app.models.field import Field
from app.models.input_cost import InputCost
from app.models.soil_test import SoilTest
from app.services.economic_service import EconomicService


def _build_field() -> Field:
    return Field(
        name="North Parcel",
        location_name="North",
        latitude=39.0,
        longitude=-94.0,
        area_hectares=10.0,
        slope_percent=3.0,
        irrigation_available=True,
        drainage_quality="good",
    )


def _build_crop() -> CropProfile:
    return CropProfile(
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
        crop_price=CropPrice(price_per_ton=210.0),
        input_cost=InputCost(fertilizer_cost=240.0, water_cost=165.0, labor_cost=130.0),
    )


def _build_soil() -> SoilTest:
    return SoilTest(
        field_id=1,
        ph=6.5,
        organic_matter_percent=4.0,
        nitrogen_ppm=40.0,
        phosphorus_ppm=25.0,
        potassium_ppm=180.0,
        depth_cm=120.0,
        ec=1.2,
    )


def _normalized_explanation_payload(explanation) -> dict[str, object]:
    payload = explanation.model_dump()
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        metadata.pop("generated_at", None)
        debug_info = metadata.get("debug_info")
        if isinstance(debug_info, dict):
            risk_provider_metadata = debug_info.get("risk_provider_metadata")
            if isinstance(risk_provider_metadata, dict):
                risk_provider_metadata.pop("generated_at", None)
    return payload


def test_contract_aliases_export_requested_and_legacy_names():
    assert YieldPredictionProvider is YieldPredictor
    assert RiskScoringProvider is RiskScorer
    assert RiskAssessmentInput is RiskScoringRequest
    assert TextExtractionProvider is ExtractionProvider
    assert isinstance(YieldPredictionOrchestrator(db=None, provider=StubYieldPredictor()), YieldPredictionServiceClient)


def test_yield_prediction_contract_builds_input_and_adapts_output():
    input_data = YieldPredictionInput(
        field=YieldFieldSummary(
            field_id=12,
            name="North Parcel",
            area_hectares=10.0,
            slope_percent=3.0,
            irrigation_available=True,
            drainage_quality="good",
            elevation_meters=None,
            infrastructure_score=0,
            water_source_type=None,
            aspect=None,
        ),
        soil=YieldSoilSummary(
            soil_test_id=3,
            ph=6.5,
            ec=1.2,
            organic_matter_percent=4.0,
            nitrogen_ppm=40.0,
            phosphorus_ppm=25.0,
            potassium_ppm=180.0,
            depth_cm=120.0,
            water_holding_capacity=None,
            texture_class=None,
            drainage_class=None,
            sample_date=None,
        ),
        crop=YieldCropSummary(
            crop_id=7,
            crop_name="Wheat",
            water_requirement_level="medium",
            drainage_requirement="good",
            salinity_tolerance="moderate",
            rooting_depth_cm=120.0,
            slope_tolerance=10.0,
            optimal_temp_min_c=None,
            optimal_temp_max_c=None,
            rainfall_requirement_mm=None,
            frost_tolerance_days=None,
            heat_tolerance_days=None,
            organic_matter_preference="moderate",
        ),
        climate=YieldClimateSummary(
            avg_temp=19.0,
            total_rainfall=240.0,
            frost_days=3,
            heat_days=1,
        ),
    )
    output = YieldPredictionOutput(
        predicted_yield=7.6,
        yield_range_min=6.8,
        yield_range_max=8.4,
        metadata=AITraceMetadata(
            provider_name="deterministic_stub_provider",
            provider_version="v1",
            generated_at=datetime.now(timezone.utc),
            confidence=0.74,
        ),
    )

    adapted = adapt_yield_prediction_output(input_data, output)

    assert adapted.field_id == 12
    assert adapted.crop_id == 7
    assert adapted.predicted_yield_per_hectare == 7.6
    assert adapted.predicted_yield_min == 6.8
    assert adapted.predicted_yield_max == 8.4
    assert adapted.predicted_yield_range.min == 6.8
    assert adapted.predicted_yield_range.max == 8.4
    assert adapted.confidence_score == 0.74
    assert adapted.training_source == "deterministic_stub_provider"
    assert adapted.model_version == "v1"
    assert adapted.metadata.provider_name == "deterministic_stub_provider"
    assert adapted.feature_snapshot["has_soil_test"] is True
    assert adapted.feature_snapshot["has_climate_summary"] is True
    assert adapted.feature_snapshot["generated_at"].endswith("+00:00")


def test_rule_based_explanation_provider_new_request_api_matches_legacy_helpers():
    field = _build_field()
    crop = _build_crop()
    soil = _build_soil()
    result = calculate_suitability(field, crop, soil)
    provider = RuleBasedExplanationProvider()
    request = SuitabilityExplanationRequest(
        result=result,
        field_obj=field,
        crop=crop,
    )

    canonical = provider.explain(build_explanation_input_from_suitability_request(request))
    from_request = adapt_explanation_output(canonical)
    legacy = provider.build_suitability_explanation(result, field)

    assert _normalized_explanation_payload(from_request) == _normalized_explanation_payload(legacy)
    assert canonical.provider_name == "rule_based"
    assert canonical.provider_version == "v1"
    assert canonical.confidence_note
    assert canonical.generated_at.tzinfo is not None


def test_explanation_contract_builds_input_and_adapts_output():
    field = _build_field()
    crop = _build_crop()
    soil = _build_soil()
    result = calculate_suitability(field, crop, soil)
    input_data = build_explanation_input_from_suitability_request(
        SuitabilityExplanationRequest(
            result=result,
            field_obj=field,
            crop=crop,
        )
    )
    output = ExplanationOutput(
        short_explanation="This field ranked highly because pH is within ideal range.",
        detailed_explanation="Field 'North Parcel' is highly suitable based on the current scoring results.",
        strengths=["pH is within ideal range."],
        weaknesses=[],
        risks=[],
        confidence_note="Confidence is moderate because the explanation is derived from deterministic scoring inputs.",
        metadata=AITraceMetadata(
            provider_name="rule_based",
            provider_version="v1",
            generated_at=datetime.now(timezone.utc),
            confidence=0.78,
        ),
    )

    adapted = adapt_explanation_output(output)

    assert input_data.ranking_result.field_name == "North Parcel"
    assert input_data.ranking_result.crop_name == "Wheat"
    assert input_data.ranking_result.ranking_score == result.total_score
    assert input_data.score_breakdown["ph_compatibility"].status == result.score_breakdown["ph_compatibility"].status.value
    assert adapted.model_dump() == {
        "short_explanation": "This field ranked highly because pH is within ideal range.",
        "detailed_explanation": "Field 'North Parcel' is highly suitable based on the current scoring results.",
        "strengths": ["pH is within ideal range."],
        "weaknesses": [],
        "risks": [],
        "metadata": {
            "provider_name": "rule_based",
            "provider_version": "v1",
            "generated_at": output.generated_at,
            "confidence": 0.78,
            "debug_info": None,
        },
    }
    assert output.generated_at.tzinfo is not None


def test_explanation_contract_supports_canonical_dataclasses_directly():
    output = ExplanationOutput(
        short_explanation="This field ranked highly because irrigation is available.",
        detailed_explanation="Field 'North Parcel' remains suitable based on deterministic scoring inputs.",
        strengths=["Field has irrigation available."],
        weaknesses=["Drainage is below crop requirement."],
        risks=["Drainage is below crop requirement."],
        confidence_note="Confidence is moderate because the explanation reflects deterministic scoring inputs with limiting factors.",
        metadata=AITraceMetadata(
            provider_name="rule_based",
            provider_version="v1",
            generated_at=datetime.now(timezone.utc),
            confidence=0.72,
        ),
    )
    input_data = ExplanationInput(
        ranking_result=ExplanationRankingSummary(
            field_id=1,
            field_name="North Parcel",
            crop_id=1,
            crop_name="Wheat",
            rank=1,
            total_score=82.0,
            ranking_score=82.0,
            economic_score=0.0,
            estimated_profit=None,
        ),
        score_breakdown={
            "ph_compatibility": ExplanationScoreComponent(
                key="ph_compatibility",
                label="Soil pH",
                weight=1.0,
                awarded_points=15.0,
                max_points=15.0,
                status="ideal",
                reasons=["pH is within ideal range."],
            )
        },
        blockers=[],
        reasons=["pH is within ideal range."],
        penalties=[ExplanationPenalty(dimension="drainage", points_lost=4.0, message="Drainage is below crop requirement.")],
    )

    assert input_data.ranking_result.field_name == "North Parcel"
    assert input_data.score_breakdown["ph_compatibility"].status == "ideal"
    assert adapt_explanation_output(output).short_explanation.startswith("This field ranked highly")


def test_rule_based_risk_provider_new_request_api_matches_legacy_output():
    field = _build_field()
    crop = _build_crop()
    soil = _build_soil()
    result = calculate_suitability(field, crop, soil)
    provider = RuleBasedRiskScoringProvider()
    request = RiskScoringRequest(
        breakdown=result.score_breakdown,
        blockers=result.blockers,
    )

    assert provider.score(request).risks == provider.collect_risks(request)


def test_rule_based_extraction_provider_new_request_api_matches_legacy_output():
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Normalized text.",
                    }
                ],
            }
        ]
    }
    provider = RuleBasedTextExtractionProvider()

    assert provider.extract(ExtractionRequest(payload=payload)).text == provider.extract_output_text(payload)


def test_extraction_contract_builds_canonical_input_and_output():
    payload = {
        "output": [
            {
                "content": [
                    {
                        "text": "Normalized fertilizer guidance.",
                    }
                ]
            }
        ]
    }
    input_data = build_extraction_input_from_payload(
        payload,
        source_url="https://example.com/fertilizer",
        source_type="webpage",
        extraction_kind="fertilizer",
    )
    output = ExtractionOutput(
        normalized_json={
            "text": "Structured fertilizer extraction",
            "fertilizer_name": "NPK 20-20-20",
        },
        missing_fields=["application_window"],
        metadata=AITraceMetadata(
            provider_name="deterministic_stub_provider",
            provider_version="v1",
            generated_at=datetime.now(timezone.utc),
            confidence=0.83,
        ),
    )

    assert input_data.raw_text == "Normalized fertilizer guidance."
    assert input_data.source_url == "https://example.com/fertilizer"
    assert input_data.source_type == "webpage"
    assert input_data.extraction_kind == "fertilizer"
    assert output.text == "Structured fertilizer extraction"
    assert output.missing_fields == ["application_window"]
    assert output.provider_name == "deterministic_stub_provider"
    assert output.provider_version == "v1"
    assert output.confidence == 0.83


def test_xgboost_yield_provider_new_request_api_matches_legacy_wrappers(db, tmp_path):
    field = _build_field()
    crop = _build_crop()
    db.add_all([field, crop])
    db.commit()

    provider = XGBoostYieldPredictionProvider(db, model_dir=tmp_path / "yield_model")
    request = build_yield_prediction_input_from_entities(field, crop)
    orchestrator = YieldPredictionOrchestrator(db, provider=provider, model_dir=tmp_path / "yield_model")

    direct_output = provider.predict(request)
    adapted_output = adapt_yield_prediction_output(request, direct_output)
    orchestrated_output = orchestrator.predict_for_entities(field, crop)

    assert direct_output.generated_at.tzinfo is not None
    adapted_payload = adapted_output.model_dump()
    orchestrated_payload = orchestrated_output.model_dump()
    adapted_generated_at = adapted_payload["feature_snapshot"].pop("generated_at")
    orchestrated_generated_at = orchestrated_payload["feature_snapshot"].pop("generated_at")
    adapted_metadata_generated_at = adapted_payload["metadata"].pop("generated_at")
    orchestrated_metadata_generated_at = orchestrated_payload["metadata"].pop("generated_at")

    assert adapted_generated_at.endswith("+00:00")
    assert orchestrated_generated_at.endswith("+00:00")
    assert adapted_metadata_generated_at.tzinfo is not None
    assert orchestrated_metadata_generated_at.tzinfo is not None
    assert adapted_payload == orchestrated_payload


def test_economic_service_accepts_stub_predictor_using_new_protocol_only(db):
    stub = StubYieldPredictor()
    service = EconomicService(
        db,
        yield_prediction_service=YieldPredictionOrchestrator(db=None, provider=stub),
    )
    field = _build_field()
    crop = _build_crop()

    assessment = service.calculate_profit(field, crop)

    assert stub.requests
    assert assessment.estimated_profit == 9980.0
    assert assessment.yield_prediction is not None
