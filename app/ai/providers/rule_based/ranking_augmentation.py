"""Rule-based ranking augmentation provider."""

from __future__ import annotations

from app.ai.contracts.ranking import RankingAugmentationCandidate, RankingAugmentationProvider


def _economic_score_for_profit(
    estimated_profit: float | None,
    *,
    max_positive_profit: float,
    max_loss_magnitude: float,
) -> float:
    if estimated_profit is None:
        return 0.0
    if estimated_profit == 0:
        return 50.0
    if estimated_profit > 0:
        if max_positive_profit <= 0:
            return 100.0
        return round(min(100.0, 50.0 + ((estimated_profit / max_positive_profit) * 50.0)), 2)

    if max_loss_magnitude <= 0:
        return 0.0
    return round(max(0.0, 50.0 - ((abs(estimated_profit) / max_loss_magnitude) * 50.0)), 2)


class RuleBasedRankingAugmentationProvider(RankingAugmentationProvider):
    """Default provider that augments ranking with deterministic economics."""

    def apply_ranking_scores(
        self,
        candidates: list[RankingAugmentationCandidate],
        *,
        economics_enabled: bool,
    ) -> None:
        positive_profits = [
            candidate.economic_assessment.estimated_profit
            for candidate in candidates
            if candidate.economic_assessment is not None
            and candidate.economic_assessment.estimated_profit is not None
            and candidate.economic_assessment.estimated_profit > 0
        ]
        loss_magnitudes = [
            abs(candidate.economic_assessment.estimated_profit)
            for candidate in candidates
            if candidate.economic_assessment is not None
            and candidate.economic_assessment.estimated_profit is not None
            and candidate.economic_assessment.estimated_profit < 0
        ]
        max_positive_profit = max(positive_profits, default=0.0)
        max_loss_magnitude = max(loss_magnitudes, default=0.0)

        for candidate in candidates:
            if economics_enabled:
                estimated_profit = (
                    candidate.economic_assessment.estimated_profit
                    if candidate.economic_assessment is not None
                    else None
                )
                candidate.economic_score = _economic_score_for_profit(
                    estimated_profit,
                    max_positive_profit=max_positive_profit,
                    max_loss_magnitude=max_loss_magnitude,
                )
                if candidate.scoring_result.total_score == 0.0:
                    candidate.ranking_score = 0.0
                else:
                    candidate.ranking_score = round(
                        (candidate.scoring_result.total_score * 0.7) + (candidate.economic_score * 0.3),
                        2,
                    )
            else:
                candidate.economic_score = 0.0
                candidate.ranking_score = candidate.scoring_result.total_score
