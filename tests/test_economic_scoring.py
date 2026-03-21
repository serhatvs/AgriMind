from app.engines.economic_scoring import EconomicScorer, score_profitability
from app.services.economic_feature_builder import (
    CropEconomicProfileSnapshot,
    EconomicClimateStressFeatures,
    EconomicCropFeatures,
    EconomicFeatureInput,
    EconomicFieldFeatures,
)


def _feature_input(*, predicted_yield: float, irrigation_available: bool = True) -> EconomicFeatureInput:
    return EconomicFeatureInput(
        predicted_yield=predicted_yield,
        predicted_yield_confidence=0.8,
        field=EconomicFieldFeatures(
            irrigation_available=irrigation_available,
            infrastructure_score=72,
            area_hectares=20.0,
            location_name="Economic Valley",
        ),
        crop=EconomicCropFeatures(
            crop_name="Corn",
            water_requirement_level="high",
            rooting_depth_cm=150.0,
        ),
        climate_stress=EconomicClimateStressFeatures(
            frost_days=1,
            heat_days=3,
            weather_record_count=30,
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


def test_economic_scorer_calculates_revenue_cost_and_profit():
    result = EconomicScorer().score(_feature_input(predicted_yield=8.4))

    assert result.estimated_revenue == 35280.0
    assert result.estimated_cost is not None
    assert result.estimated_profit is not None
    assert result.estimated_profit > 0
    assert result.economic_score > 0
    assert result.cost_breakdown is not None


def test_economic_score_normalization_rewards_better_profitability():
    high_profit_score = score_profitability(
        estimated_revenue=36000.0,
        estimated_cost=12000.0,
        estimated_profit=24000.0,
        area_hectares=20.0,
        confidence=0.82,
    )
    low_profit_score = score_profitability(
        estimated_revenue=18000.0,
        estimated_cost=17000.0,
        estimated_profit=1000.0,
        area_hectares=20.0,
        confidence=0.82,
    )

    assert high_profit_score > low_profit_score
    assert 0 <= low_profit_score <= 100
    assert 0 <= high_profit_score <= 100
