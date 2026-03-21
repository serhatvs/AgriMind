"""Contracts for risk-scoring providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from app.ai.contracts.metadata import AITraceMetadata
from app.engines.scoring_types import ScoreBlocker, ScoreComponent


@dataclass(slots=True)
class RiskScoringRequest:
    """Input payload used to derive material risk messages."""

    breakdown: dict[str, ScoreComponent] = field(default_factory=dict)
    blockers: list[ScoreBlocker] = field(default_factory=list)


@dataclass(slots=True)
class RiskAssessment:
    """Structured risk assessment returned by a risk scorer."""

    risks: list[str] = field(default_factory=list)
    metadata: AITraceMetadata = field(
        default_factory=lambda: AITraceMetadata(
            provider_name="unknown",
            provider_version=None,
            generated_at=datetime.now(timezone.utc),
            confidence=None,
        )
    )

    @property
    def provider_name(self) -> str:
        return self.metadata.provider_name

    @property
    def provider_version(self) -> str | None:
        return self.metadata.provider_version

    @property
    def generated_at(self):
        return self.metadata.generated_at

    @property
    def confidence(self) -> float | None:
        return self.metadata.confidence

    @property
    def debug_info(self) -> dict[str, object] | None:
        return self.metadata.debug_info


class RiskScorer(Protocol):
    """Aggregate material risks from typed scoring inputs."""

    def score(self, request: RiskScoringRequest) -> RiskAssessment:
        """Return the ordered risk messages derived from `request`."""


RiskAssessmentInput = RiskScoringRequest
RiskScoringProvider = RiskScorer
