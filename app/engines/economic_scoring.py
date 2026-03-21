"""Deterministic profitability scoring for field and crop combinations."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.economic_feature_builder import EconomicFeatureInput


@dataclass(frozen=True, slots=True)
class EconomicCostBreakdown:
    """Detailed cost components used to estimate profitability."""

    base_cost: float
    irrigation_cost: float
    fertilizer_cost: float
    labor_cost: float
    risk_cost: float


@dataclass(frozen=True, slots=True)
class EconomicScoringResult:
    """Structured profitability scoring result."""

    economic_score: float
    estimated_revenue: float | None
    estimated_cost: float | None
    estimated_profit: float | None
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    cost_breakdown: EconomicCostBreakdown | None = None


class EconomicScorer:
    """Score profitability using normalized economic features."""

    def score(self, features: EconomicFeatureInput) -> EconomicScoringResult:
        """Estimate revenue, cost, profit, and a normalized economic score."""

        profile = features.economic_profile
        predicted_yield = features.predicted_yield
        if profile is None or predicted_yield is None or features.field.area_hectares <= 0:
            return EconomicScoringResult(
                economic_score=0.0,
                estimated_revenue=None,
                estimated_cost=None,
                estimated_profit=None,
                weaknesses=["Economic data unavailable for this crop."],
                risks=["Profitability could not be estimated from the current economic inputs."],
            )

        estimated_revenue = round(
            predicted_yield * profile.average_market_price_per_unit * features.field.area_hectares,
            2,
        )

        base_cost_total = profile.base_cost_per_hectare * features.field.area_hectares
        fertilizer_cost = base_cost_total * profile.fertilizer_cost_factor
        labor_cost = base_cost_total * profile.labor_cost_factor
        irrigation_cost = (
            base_cost_total * profile.irrigation_cost_factor
            if features.field.irrigation_available
            else 0.0
        )
        risk_index = _risk_index(features)
        risk_cost = base_cost_total * profile.risk_cost_factor * risk_index
        estimated_cost = round(
            base_cost_total + fertilizer_cost + labor_cost + irrigation_cost + risk_cost,
            2,
        )
        estimated_profit = round(estimated_revenue - estimated_cost, 2)

        strengths: list[str] = []
        weaknesses: list[str] = []
        risks: list[str] = []

        profit_margin = estimated_profit / estimated_revenue if estimated_revenue > 0 else -1.0
        roi = estimated_profit / estimated_cost if estimated_cost > 0 else -1.0
        profit_per_hectare = estimated_profit / features.field.area_hectares

        if estimated_profit > 0 and profit_margin >= 0.35:
            strengths.append("This field is highly profitable due to strong yield and favorable market price.")
        elif estimated_profit > 0:
            strengths.append("This field is profitable under the current market and yield assumptions.")

        if features.field.irrigation_available and irrigation_cost > base_cost_total * 0.15:
            weaknesses.append("High irrigation cost reduces overall profitability.")
        if estimated_profit <= 0:
            weaknesses.append("Despite good agronomic conditions, low market price lowers ranking.")

        climate_stress = features.climate_stress
        if climate_stress is not None and climate_stress.frost_days > 0:
            risks.append("Recent frost exposure could increase downside production risk.")
        if climate_stress is not None and climate_stress.heat_days >= 4:
            risks.append("Recent heat stress could raise downside production cost.")
        if features.predicted_yield_confidence is not None and features.predicted_yield_confidence < 0.6:
            risks.append("Profitability confidence is reduced because yield confidence is limited.")

        if not strengths and estimated_profit is not None and estimated_profit > 0:
            strengths.append("Profitability remains positive for this field and crop combination.")
        if not weaknesses and estimated_profit is not None and estimated_profit <= 0:
            weaknesses.append("Low expected margin reduces the economic attractiveness of this field.")

        economic_score = _economic_score(
            profit_margin=profit_margin,
            roi=roi,
            profit_per_hectare=profit_per_hectare,
            total_profit=estimated_profit,
            confidence=features.predicted_yield_confidence,
        )

        return EconomicScoringResult(
            economic_score=economic_score,
            estimated_revenue=estimated_revenue,
            estimated_cost=estimated_cost,
            estimated_profit=estimated_profit,
            strengths=strengths,
            weaknesses=weaknesses,
            risks=risks,
            cost_breakdown=EconomicCostBreakdown(
                base_cost=round(base_cost_total, 2),
                irrigation_cost=round(irrigation_cost, 2),
                fertilizer_cost=round(fertilizer_cost, 2),
                labor_cost=round(labor_cost, 2),
                risk_cost=round(risk_cost, 2),
            ),
        )


def _risk_index(features: EconomicFeatureInput) -> float:
    climate = features.climate_stress
    stress = 0.0
    if climate is not None:
        stress += min(climate.frost_days / 10.0, 0.5)
        stress += min(climate.heat_days / 12.0, 0.5)
        if climate.weather_record_count and climate.weather_record_count < 14:
            stress += 0.1
    if features.field.infrastructure_score is not None:
        stress += max(0.0, (65 - features.field.infrastructure_score) / 100.0)
    if not features.field.irrigation_available and (features.crop.water_requirement_level or "").lower() == "high":
        stress += 0.2
    return min(stress, 1.0)


def _economic_score(
    *,
    profit_margin: float,
    roi: float,
    profit_per_hectare: float,
    total_profit: float,
    confidence: float | None,
) -> float:
    margin_score = _bounded_score(profit_margin, lower=-0.25, upper=0.55)
    roi_score = _bounded_score(roi, lower=-0.25, upper=1.0)
    density_score = _bounded_score(profit_per_hectare, lower=-500.0, upper=2500.0)
    profit_score = _bounded_score(total_profit, lower=-2000.0, upper=50000.0)
    base_score = (
        (margin_score * 0.35)
        + (roi_score * 0.25)
        + (density_score * 0.20)
        + (profit_score * 0.20)
    )
    confidence_factor = 0.85 + (0.15 * (confidence if confidence is not None else 0.65))
    return round(max(0.0, min(base_score * confidence_factor, 100.0)), 2)


def score_profitability(
    *,
    estimated_revenue: float,
    estimated_cost: float,
    estimated_profit: float,
    area_hectares: float,
    confidence: float | None,
) -> float:
    """Normalize a profitability outcome into a 0-100 economic score."""

    profit_margin = estimated_profit / estimated_revenue if estimated_revenue > 0 else -1.0
    roi = estimated_profit / estimated_cost if estimated_cost > 0 else -1.0
    profit_per_hectare = estimated_profit / area_hectares if area_hectares > 0 else estimated_profit
    return _economic_score(
        profit_margin=profit_margin,
        roi=roi,
        profit_per_hectare=profit_per_hectare,
        total_profit=estimated_profit,
        confidence=confidence,
    )


def _bounded_score(value: float, *, lower: float, upper: float) -> float:
    if upper <= lower:
        return 0.0
    normalized = (value - lower) / (upper - lower)
    return max(0.0, min(normalized * 100.0, 100.0))
