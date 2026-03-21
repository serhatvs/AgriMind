"""Rule-based ranking augmentation provider."""

from __future__ import annotations

from app.ai.contracts.ranking import RankingAugmentationCandidate, RankingAugmentationProvider
from app.config import settings
from app.engines.economic_scoring import score_profitability


def _weighted_average(values: list[tuple[float, float]]) -> float:
    total_weight = sum(weight for _, weight in values if weight > 0)
    if total_weight <= 0:
        return 0.0
    weighted_total = sum(value * weight for value, weight in values if weight > 0)
    return round(weighted_total / total_weight, 2)


class RuleBasedRankingAugmentationProvider(RankingAugmentationProvider):
    """Default provider that augments ranking with deterministic economics."""

    def apply_ranking_scores(
        self,
        candidates: list[RankingAugmentationCandidate],
        *,
        economics_enabled: bool,
    ) -> None:
        economic_scoring_enabled = economics_enabled and settings.ENABLE_ECONOMIC_SCORING

        for candidate in candidates:
            agronomic_score = candidate.scoring_result.agronomic_score
            climate_score = candidate.scoring_result.climate_score

            if economic_scoring_enabled:
                assessment = candidate.economic_assessment
                if assessment is None:
                    candidate.economic_score = 0.0
                elif assessment.economic_score > 0:
                    candidate.economic_score = round(assessment.economic_score, 2)
                elif (
                    assessment.estimated_revenue is not None
                    and assessment.estimated_cost is not None
                    and assessment.estimated_profit is not None
                ):
                    candidate.economic_score = score_profitability(
                        estimated_revenue=assessment.estimated_revenue,
                        estimated_cost=assessment.estimated_cost,
                        estimated_profit=assessment.estimated_profit,
                        area_hectares=getattr(candidate.field_obj, "area_hectares", 1.0) or 1.0,
                        confidence=(
                            candidate.yield_prediction.confidence_score
                            if getattr(candidate, "yield_prediction", None) is not None
                            else candidate.scoring_result.confidence_score
                        ),
                    )
                else:
                    candidate.economic_score = 0.0
            else:
                candidate.economic_score = 0.0

            if candidate.scoring_result.total_score == 0.0:
                candidate.total_score = 0.0
                candidate.ranking_score = 0.0
                continue

            weighted_components: list[tuple[float, float]] = [
                (agronomic_score, settings.AGRONOMIC_SCORE_WEIGHT),
            ]
            if climate_score is not None:
                weighted_components.append((climate_score, settings.CLIMATE_SCORE_WEIGHT))
            if economic_scoring_enabled and candidate.economic_assessment is not None:
                weighted_components.append((candidate.economic_score, settings.ECONOMIC_SCORE_WEIGHT))

            composite_score = _weighted_average(weighted_components)
            candidate.total_score = composite_score
            candidate.ranking_score = composite_score
