from types import SimpleNamespace

from app.services.economic_feature_builder import (
    CropEconomicProfileSnapshot,
    EconomicFeatureBuilder,
)
from app.schemas.ai_metadata import AITraceMetadataRead
from app.schemas.weather_history import ClimateSummary
from app.schemas.yield_prediction import YieldPredictionRange, YieldPredictionResult


def _yield_prediction() -> YieldPredictionResult:
    return YieldPredictionResult(
        field_id=1,
        crop_id=2,
        predicted_yield_per_hectare=8.7,
        predicted_yield_min=7.9,
        predicted_yield_max=9.6,
        predicted_yield_range=YieldPredictionRange(min=7.9, max=9.6),
        confidence_score=0.81,
        model_version="yield-xgb-v1",
        training_source="test",
        feature_snapshot={},
        metadata=AITraceMetadataRead(
            provider_name="test",
            provider_version="yield-xgb-v1",
            generated_at="2026-03-21T00:00:00Z",
            confidence=0.81,
            debug_info=None,
        ),
    )


def test_economic_feature_builder_normalizes_entities():
    builder = EconomicFeatureBuilder()
    features = builder.build_from_entities(
        SimpleNamespace(
            irrigation_available=True,
            infrastructure_score=73,
            area_hectares=18.5,
            location_name="Konya",
        ),
        SimpleNamespace(
            crop_name="Corn",
            water_requirement_level="high",
            rooting_depth_cm=150.0,
        ),
        yield_prediction=_yield_prediction(),
        climate_summary=ClimateSummary(
            frost_days=1,
            heat_days=4,
            weather_record_count=28,
        ),
        economic_profile=CropEconomicProfileSnapshot(
            crop_name="Corn",
            average_market_price_per_unit=210.0,
            price_unit="ton",
            base_cost_per_hectare=360.0,
            irrigation_cost_factor=0.18,
            fertilizer_cost_factor=0.22,
            labor_cost_factor=0.11,
            risk_cost_factor=0.06,
            region=None,
            source_name="static",
        ),
    )

    assert features.predicted_yield == 8.7
    assert features.predicted_yield_confidence == 0.81
    assert features.field.irrigation_available is True
    assert features.field.infrastructure_score == 73
    assert features.field.area_hectares == 18.5
    assert features.crop.crop_name == "Corn"
    assert features.crop.water_requirement_level == "high"
    assert features.climate_stress is not None
    assert features.climate_stress.frost_days == 1
    assert features.climate_stress.heat_days == 4
    assert features.economic_profile is not None
    assert features.economic_profile.average_market_price_per_unit == 210.0
