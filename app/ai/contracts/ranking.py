"""Contracts for ranking augmentation providers."""

from __future__ import annotations

from typing import Protocol

from app.engines.scoring_types import SuitabilityResult


class RankingAugmentationCandidate(Protocol):
    """Internal candidate shape consumed by ranking augmentation providers."""

    scoring_result: SuitabilityResult
    economic_assessment: object | None
    economic_score: float
    total_score: float
    ranking_score: float


class RankingAugmentationProvider(Protocol):
    """Provider contract for composing ranking scores from scored candidates."""

    def apply_ranking_scores(
        self,
        candidates: list[RankingAugmentationCandidate],
        *,
        economics_enabled: bool,
    ) -> None:
        """Mutate ranking candidates with any provider-specific score augmentation."""
