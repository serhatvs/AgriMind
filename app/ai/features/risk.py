"""Assemble risk-scoring inputs from persisted field, crop, soil, and climate data.

Example:
```python
from app.ai.features.risk import build_risk_input

risk_input = build_risk_input(db, field_id=1, crop_id=2)
print(sorted(risk_input.breakdown))
```
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.contracts.risk import RiskScoringRequest
from app.ai.contracts.suitability import SuitabilityProvider
from app.ai.features.loaders import assemble_feature_bundle
from app.ai.registry import get_ai_provider_registry
from app.engines.scoring_types import SuitabilityResult
from app.services.weather_service import WeatherService


def build_risk_input(
    db: Session,
    field_id: int,
    crop_id: int,
    *,
    suitability_provider: SuitabilityProvider | None = None,
    weather_service: WeatherService | None = None,
) -> RiskScoringRequest:
    """Load persisted data, score suitability, and assemble the risk provider input."""

    bundle = assemble_feature_bundle(
        db,
        field_id,
        crop_id,
        weather_service=weather_service,
    )
    provider = suitability_provider or get_ai_provider_registry().get_suitability_provider()
    result = provider.calculate_suitability(
        bundle.field_obj,
        bundle.crop,
        bundle.soil_test,
        climate_summary=bundle.climate_summary,
    )
    return build_risk_input_from_suitability_result(result)


def build_risk_input_from_suitability_result(result: SuitabilityResult) -> RiskScoringRequest:
    """Map a suitability result into the existing risk provider contract."""

    return RiskScoringRequest(
        breakdown=result.score_breakdown,
        blockers=result.blockers,
    )
