"""Provider-based recommendation orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.contracts.explanation import (
    ExplanationProvider,
    SuitabilityExplanationRequest,
    adapt_explanation_output,
    build_explanation_input_from_suitability_request,
)
from app.ai.features.loaders import build_feature_summary_bundle
from app.ai.contracts.suitability import SuitabilityProvider
from app.ai.registry import get_ai_provider_registry
from app.engines.scoring_types import SuitabilityResult
from app.models.crop_profile import CropProfile
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.schemas.explanation import FieldExplanation
from app.schemas.weather_history import ClimateSummary


@dataclass(slots=True)
class RecommendationResult:
    """Structured recommendation output used by compatibility façades."""

    suitability: SuitabilityResult
    explanation: FieldExplanation


class RecommendationOrchestrator:
    """Compose suitability and explanation providers for single-field recommendations."""

    def __init__(
        self,
        *,
        suitability_provider: SuitabilityProvider | None = None,
        explanation_provider: ExplanationProvider | None = None,
    ) -> None:
        registry = get_ai_provider_registry()
        self.suitability_provider = suitability_provider or registry.get_suitability_provider()
        self.explanation_provider = explanation_provider or registry.get_explanation_provider()

    def generate(
        self,
        field_obj: Field,
        crop: CropProfile,
        soil_test: SoilTest | None,
        *,
        climate_summary: ClimateSummary | None = None,
    ) -> RecommendationResult:
        """Generate suitability and explanation output for one field/crop pair."""

        suitability = self.suitability_provider.calculate_suitability(
            field_obj,
            crop,
            soil_test,
            climate_summary=climate_summary,
        )
        explanation = adapt_explanation_output(
            self.explanation_provider.explain(
                build_explanation_input_from_suitability_request(
                    SuitabilityExplanationRequest(
                        result=suitability,
                        field_obj=field_obj,
                        crop=crop,
                        feature_context=build_feature_summary_bundle(
                            field_obj,
                            crop,
                            soil_test=soil_test,
                            climate_summary=climate_summary,
                        ),
                    )
                )
            )
        )
        return RecommendationResult(suitability=suitability, explanation=explanation)
