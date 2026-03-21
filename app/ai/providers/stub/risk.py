"""Deterministic stub risk scorer used in development and tests."""

from __future__ import annotations

from datetime import datetime, timezone

from app.ai.contracts.metadata import AITraceMetadata
from app.ai.contracts.risk import RiskAssessment, RiskScorer, RiskScoringRequest
from app.ai.providers.stub.common import dedupe_messages, with_stub_suffix
from app.engines.scoring_types import ScoreStatus


class StubRiskScorer(RiskScorer):
    """Return stable placeholder risks while preserving request-driven ordering."""

    def score(self, request: RiskScoringRequest) -> RiskAssessment:
        """Return deterministic risk messages derived from blockers and weak components."""

        risks = [with_stub_suffix(blocker.message) for blocker in request.blockers]

        for key in sorted(request.breakdown):
            component = request.breakdown[key]
            if component.status not in {ScoreStatus.BLOCKED, ScoreStatus.LIMITED, ScoreStatus.MISSING}:
                continue

            reasons = component.reasons or [f"{component.label} requires follow-up review"]
            risks.extend(with_stub_suffix(reason) for reason in reasons)

        deduped = dedupe_messages(risks)
        if not deduped:
            deduped = [
                with_stub_suffix("No material agronomic risks detected from current stub inputs"),
            ]
        return RiskAssessment(
            risks=deduped,
            metadata=AITraceMetadata(
                provider_name="deterministic_stub_provider",
                provider_version="v1",
                generated_at=datetime.now(timezone.utc),
                confidence=0.88 if request.blockers else (0.74 if deduped else 0.66),
                debug_info={
                    "stub": True,
                    "blocker_count": len(request.blockers),
                    "component_count": len(request.breakdown),
                    "risk_count": len(deduped),
                },
            ),
        )

    def collect_risks(self, payload: RiskScoringRequest) -> list[str]:
        """Compatibility wrapper that returns only the risk strings."""

        return self.score(payload).risks
