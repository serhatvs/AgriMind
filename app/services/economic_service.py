"""Economic scoring helpers built on top of yield prediction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.ai.contracts.yield_prediction import YieldPredictionContext, YieldPredictionServiceClient
from app.models.crop_price import CropPrice
from app.models.input_cost import InputCost
from app.schemas.yield_prediction import YieldPredictionResult
from app.services.yield_prediction_service import YieldPredictionService

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile
    from app.models.field import Field
    from app.models.soil_test import SoilTest
    from app.schemas.weather_history import ClimateSummary


@dataclass(slots=True)
class EconomicAssessment:
    """Profitability estimate for a field and crop combination."""

    estimated_revenue: float | None
    estimated_cost: float | None
    estimated_profit: float | None
    reasons: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
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

    def estimate_revenue(
        self,
        yield_per_hectare: float,
        price_per_ton: float,
        area_hectares: float,
    ) -> float:
        """Estimate total field revenue from yield, price, and field area."""

        return round(yield_per_hectare * price_per_ton * area_hectares, 2)

    def estimate_cost(self, field_obj: "Field", crop: "CropProfile") -> float | None:
        """Estimate total field input cost using crop-scoped per-hectare cost values."""

        input_cost = crop.input_cost or self._get_input_cost(crop.id)
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
        """Estimate revenue, cost, and profit for a field/crop pairing."""

        crop_price = crop.crop_price or self._get_crop_price(crop.id)
        input_cost = crop.input_cost or self._get_input_cost(crop.id)
        if crop_price is None or input_cost is None:
            return EconomicAssessment(
                estimated_revenue=None,
                estimated_cost=None,
                estimated_profit=None,
                reasons=["Economic data unavailable for this crop."],
            )

        prediction = yield_prediction or self.yield_prediction_service.predict_from_context(
            YieldPredictionContext(
                field_obj=field_obj,
                crop=crop,
                soil_test=soil_test,
                climate_summary=climate_summary,
            )
        )
        estimated_revenue = self.estimate_revenue(
            prediction.predicted_yield_per_hectare,
            crop_price.price_per_ton,
            field_obj.area_hectares,
        )
        estimated_cost = self.estimate_cost(field_obj, crop)
        if estimated_cost is None:
            return EconomicAssessment(
                estimated_revenue=None,
                estimated_cost=None,
                estimated_profit=None,
                reasons=["Economic data unavailable for this crop."],
                yield_prediction=prediction,
            )

        estimated_profit = round(estimated_revenue - estimated_cost, 2)
        strengths: list[str] = []
        weaknesses: list[str] = []

        cost_ratio = estimated_cost / estimated_revenue if estimated_revenue > 0 else 1.0
        water_cost_share = (
            input_cost.water_cost / (input_cost.fertilizer_cost + input_cost.water_cost + input_cost.labor_cost)
            if (input_cost.fertilizer_cost + input_cost.water_cost + input_cost.labor_cost) > 0
            else 0.0
        )

        if estimated_profit > 0 and cost_ratio <= 0.55:
            strengths.append("High profit due to high yield and low cost.")
        elif estimated_profit > 0:
            strengths.append("Profitability is positive for this field and crop combination.")

        if estimated_profit <= 0 and field_obj.irrigation_available and water_cost_share >= 0.25:
            weaknesses.append("Low profitability due to irrigation cost.")
        elif estimated_profit <= 0:
            weaknesses.append("Low profitability due to low expected yield.")
        elif field_obj.irrigation_available and water_cost_share >= 0.3 and estimated_profit < estimated_cost:
            weaknesses.append("Low profitability due to irrigation cost.")

        if not strengths and not weaknesses:
            strengths.append("Profitability is near break-even.")

        reasons = strengths + weaknesses
        return EconomicAssessment(
            estimated_revenue=estimated_revenue,
            estimated_cost=estimated_cost,
            estimated_profit=estimated_profit,
            reasons=reasons,
            strengths=strengths,
            weaknesses=weaknesses,
            yield_prediction=prediction,
        )

    def _get_crop_price(self, crop_id: int) -> CropPrice | None:
        return self.db.query(CropPrice).filter(CropPrice.crop_id == crop_id).first()

    def _get_input_cost(self, crop_id: int) -> InputCost | None:
        return self.db.query(InputCost).filter(InputCost.crop_id == crop_id).first()
