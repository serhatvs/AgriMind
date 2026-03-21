"""Economic scoring helpers built on top of yield prediction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.ai.contracts.yield_prediction import YieldPredictionContext, YieldPredictionServiceClient
from app.config import settings
from app.db.reflection import tables_exist
from app.engines.economic_scoring import EconomicCostBreakdown, EconomicScorer, score_profitability
from app.models.crop_economic_profile import CropEconomicProfile
from app.models.crop_price import CropPrice
from app.models.input_cost import InputCost
from app.schemas.yield_prediction import YieldPredictionResult
from app.services.economic_feature_builder import (
    CropEconomicProfileSnapshot,
    EconomicFeatureBuilder,
)
from app.services.yield_prediction_service import YieldPredictionService

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile
    from app.models.field import Field
    from app.models.soil_test import SoilTest
    from app.schemas.weather_history import ClimateSummary


@dataclass(slots=True)
class EconomicAssessment:
    """Profitability estimate for a field and crop combination."""

    economic_score: float = 0.0
    estimated_revenue: float | None = None
    estimated_cost: float | None = None
    estimated_profit: float | None = None
    reasons: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    cost_breakdown: EconomicCostBreakdown | None = None
    yield_prediction: YieldPredictionResult | None = None


class EconomicService:
    """Estimate field-level profitability for a selected crop."""

    def __init__(
        self,
        db: Session,
        *,
        yield_prediction_service: YieldPredictionServiceClient | None = None,
    ) -> None:
        self.db = db
        self.yield_prediction_service = yield_prediction_service or YieldPredictionService(db)
        self.feature_builder = EconomicFeatureBuilder()
        self.scorer = EconomicScorer()

    def estimate_revenue(
        self,
        yield_per_hectare: float,
        price_per_unit: float,
        area_hectares: float,
    ) -> float:
        """Estimate total field revenue from yield, price, and field area."""

        return round(yield_per_hectare * price_per_unit * area_hectares, 2)

    def estimate_cost(self, field_obj: "Field", crop: "CropProfile") -> float | None:
        """Estimate total field production cost from the best available economic inputs."""

        profile_snapshot = self._resolve_profile_snapshot(field_obj, crop)
        if profile_snapshot is not None:
            return self._estimate_cost_from_profile(field_obj, crop, profile_snapshot)

        input_cost = getattr(crop, "input_cost", None) or self._get_input_cost(crop.id)
        if input_cost is None:
            return None

        per_hectare_cost = input_cost.fertilizer_cost + input_cost.labor_cost
        if field_obj.irrigation_available:
            per_hectare_cost += input_cost.water_cost
        return round(per_hectare_cost * field_obj.area_hectares, 2)

    def calculate_profit(
        self,
        field_obj: "Field",
        crop: "CropProfile",
        *,
        soil_test: "SoilTest | None" = None,
        climate_summary: "ClimateSummary | None" = None,
        yield_prediction: YieldPredictionResult | None = None,
    ) -> EconomicAssessment:
        """Estimate revenue, cost, profit, and economic score for a field/crop pairing."""

        prediction = yield_prediction or self.yield_prediction_service.predict_from_context(
            YieldPredictionContext(
                field_obj=field_obj,
                crop=crop,
                soil_test=soil_test,
                climate_summary=climate_summary,
            )
        )

        if not settings.ENABLE_ECONOMIC_SCORING:
            return EconomicAssessment(
                economic_score=0.0,
                estimated_revenue=None,
                estimated_cost=None,
                estimated_profit=None,
                reasons=["Economic scoring is disabled by configuration."],
                weaknesses=["Economic scoring is disabled by configuration."],
                yield_prediction=prediction,
            )

        profile_snapshot = self._resolve_profile_snapshot(field_obj, crop)
        if profile_snapshot is not None:
            features = self.feature_builder.build_from_entities(
                field_obj,
                crop,
                yield_prediction=prediction,
                climate_summary=climate_summary,
                economic_profile=profile_snapshot,
            )
            scoring = self.scorer.score(features)
            return EconomicAssessment(
                economic_score=scoring.economic_score,
                estimated_revenue=scoring.estimated_revenue,
                estimated_cost=scoring.estimated_cost,
                estimated_profit=scoring.estimated_profit,
                reasons=_merge_messages(scoring.strengths, scoring.weaknesses, scoring.risks),
                strengths=scoring.strengths,
                weaknesses=scoring.weaknesses,
                risks=scoring.risks,
                cost_breakdown=scoring.cost_breakdown,
                yield_prediction=prediction,
            )

        crop_price = getattr(crop, "crop_price", None) or self._get_crop_price(crop.id)
        input_cost = getattr(crop, "input_cost", None) or self._get_input_cost(crop.id)
        if crop_price is None or input_cost is None:
            return EconomicAssessment(
                economic_score=0.0,
                estimated_revenue=None,
                estimated_cost=None,
                estimated_profit=None,
                reasons=["Economic data unavailable for this crop."],
                weaknesses=["Economic data unavailable for this crop."],
                risks=["Profitability could not be estimated from the current economic inputs."],
                yield_prediction=prediction,
            )

        estimated_revenue = self.estimate_revenue(
            prediction.predicted_yield_per_hectare,
            crop_price.price_per_ton,
            field_obj.area_hectares,
        )
        estimated_cost = self.estimate_cost(field_obj, crop)
        if estimated_cost is None:
            return EconomicAssessment(
                economic_score=0.0,
                estimated_revenue=None,
                estimated_cost=None,
                estimated_profit=None,
                reasons=["Economic data unavailable for this crop."],
                weaknesses=["Economic data unavailable for this crop."],
                risks=["Profitability could not be estimated from the current economic inputs."],
                yield_prediction=prediction,
            )

        estimated_profit = round(estimated_revenue - estimated_cost, 2)
        return self._build_legacy_assessment(
            field_obj=field_obj,
            crop=crop,
            crop_price=crop_price,
            input_cost=input_cost,
            prediction=prediction,
            estimated_revenue=estimated_revenue,
            estimated_cost=estimated_cost,
            estimated_profit=estimated_profit,
        )

    def _resolve_profile_snapshot(
        self,
        field_obj: "Field",
        crop: "CropProfile",
    ) -> CropEconomicProfileSnapshot | None:
        if not tables_exist(self.db, "crop_economic_profiles"):
            return None

        normalized_crop_name = str(crop.crop_name).strip().lower()
        region_name = getattr(field_obj, "location_name", None)
        query = self.db.query(CropEconomicProfile).filter(
            func.lower(CropEconomicProfile.crop_name) == normalized_crop_name
        )
        if region_name:
            profile = (
                query.filter(func.lower(CropEconomicProfile.region) == region_name.strip().lower())
                .first()
            )
            if profile is not None:
                return self._snapshot_from_model(profile)

        profile = query.filter(CropEconomicProfile.region.is_(None)).first()
        if profile is None:
            profile = query.first()
        if profile is None:
            return None
        return self._snapshot_from_model(profile)

    def _snapshot_from_model(self, profile: CropEconomicProfile) -> CropEconomicProfileSnapshot:
        return CropEconomicProfileSnapshot(
            crop_name=profile.crop_name,
            average_market_price_per_unit=profile.average_market_price_per_unit,
            price_unit=profile.price_unit,
            base_cost_per_hectare=profile.base_cost_per_hectare,
            irrigation_cost_factor=profile.irrigation_cost_factor,
            fertilizer_cost_factor=profile.fertilizer_cost_factor,
            labor_cost_factor=profile.labor_cost_factor,
            risk_cost_factor=profile.risk_cost_factor,
            region=profile.region,
            source_name=settings.DEFAULT_CROP_PRICE_SOURCE,
        )

    def _estimate_cost_from_profile(
        self,
        field_obj: "Field",
        crop: "CropProfile",
        profile: CropEconomicProfileSnapshot,
    ) -> float:
        base_cost_total = profile.base_cost_per_hectare * field_obj.area_hectares
        irrigation_cost = (
            base_cost_total * profile.irrigation_cost_factor
            if field_obj.irrigation_available
            else 0.0
        )
        fertilizer_cost = base_cost_total * profile.fertilizer_cost_factor
        labor_cost = base_cost_total * profile.labor_cost_factor
        risk_cost = base_cost_total * profile.risk_cost_factor * self._static_risk_index(field_obj, crop)
        return round(base_cost_total + irrigation_cost + fertilizer_cost + labor_cost + risk_cost, 2)

    def _static_risk_index(self, field_obj: "Field", crop: "CropProfile") -> float:
        risk_index = 0.0
        if getattr(field_obj, "infrastructure_score", None) is not None:
            risk_index += max(0.0, (65 - float(field_obj.infrastructure_score)) / 100.0)
        water_requirement = getattr(crop.water_requirement_level, "value", getattr(crop, "water_requirement_level", ""))
        if not field_obj.irrigation_available and str(water_requirement).lower() == "high":
            risk_index += 0.2
        return min(risk_index, 1.0)

    def _build_legacy_assessment(
        self,
        *,
        field_obj: "Field",
        crop: "CropProfile",
        crop_price: CropPrice,
        input_cost: InputCost,
        prediction: YieldPredictionResult,
        estimated_revenue: float,
        estimated_cost: float,
        estimated_profit: float,
    ) -> EconomicAssessment:
        strengths: list[str] = []
        weaknesses: list[str] = []
        risks: list[str] = []

        cost_ratio = estimated_cost / estimated_revenue if estimated_revenue > 0 else 1.0
        water_cost_share = (
            input_cost.water_cost
            / (input_cost.fertilizer_cost + input_cost.water_cost + input_cost.labor_cost)
            if (input_cost.fertilizer_cost + input_cost.water_cost + input_cost.labor_cost) > 0
            else 0.0
        )

        if estimated_profit > 0 and cost_ratio <= 0.55:
            strengths.append("This field is highly profitable due to strong yield and favorable market price.")
        elif estimated_profit > 0:
            strengths.append("This field is profitable under the current market and yield assumptions.")

        if field_obj.irrigation_available and water_cost_share >= 0.25:
            weaknesses.append("High irrigation cost reduces overall profitability.")
        if estimated_profit <= 0:
            weaknesses.append("Despite good agronomic conditions, low market price lowers ranking.")

        if crop_price.price_per_ton < 250.0:
            risks.append("Market price volatility could reduce realized margin.")
        if prediction.confidence_score < 0.65:
            risks.append("Profitability confidence is reduced because yield confidence is limited.")

        if not strengths and estimated_profit is not None and estimated_profit > 0:
            strengths.append("Profitability remains positive for this field and crop combination.")
        if not weaknesses and estimated_profit is not None and estimated_profit <= 0:
            weaknesses.append("Low expected margin reduces the economic attractiveness of this field.")

        economic_score = score_profitability(
            estimated_revenue=estimated_revenue,
            estimated_cost=estimated_cost,
            estimated_profit=estimated_profit,
            area_hectares=field_obj.area_hectares,
            confidence=prediction.confidence_score,
        )
        return EconomicAssessment(
            economic_score=economic_score,
            estimated_revenue=estimated_revenue,
            estimated_cost=estimated_cost,
            estimated_profit=estimated_profit,
            reasons=_merge_messages(strengths, weaknesses, risks),
            strengths=strengths,
            weaknesses=weaknesses,
            risks=risks,
            cost_breakdown=EconomicCostBreakdown(
                base_cost=round((input_cost.fertilizer_cost + input_cost.labor_cost) * field_obj.area_hectares, 2),
                irrigation_cost=round(
                    input_cost.water_cost * field_obj.area_hectares if field_obj.irrigation_available else 0.0,
                    2,
                ),
                fertilizer_cost=round(input_cost.fertilizer_cost * field_obj.area_hectares, 2),
                labor_cost=round(input_cost.labor_cost * field_obj.area_hectares, 2),
                risk_cost=0.0,
            ),
            yield_prediction=prediction,
        )

    def _get_crop_price(self, crop_id: int) -> CropPrice | None:
        if not tables_exist(self.db, "crop_prices"):
            return None
        return self.db.query(CropPrice).filter(CropPrice.crop_id == crop_id).first()

    def _get_input_cost(self, crop_id: int) -> InputCost | None:
        if not tables_exist(self.db, "input_costs"):
            return None
        return self.db.query(InputCost).filter(InputCost.crop_id == crop_id).first()


def _merge_messages(*message_sets: list[str]) -> list[str]:
    merged: list[str] = []
    for message_set in message_sets:
        for message in message_set:
            if message not in merged:
                merged.append(message)
    return merged
