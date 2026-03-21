"""Rule-based risk aggregation provider."""

from __future__ import annotations

from datetime import datetime, timezone

from app.ai.contracts.metadata import AITraceMetadata
from app.ai.contracts.risk import RiskAssessment, RiskScorer, RiskScoringRequest
from app.engines.scoring_types import ScoreStatus


def _dedupe_messages(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for message in messages:
        normalized = message.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


class RuleBasedRiskScoringProvider(RiskScorer):
    """Default provider that derives risks from deterministic scoring outputs."""

    def score(self, request: RiskScoringRequest) -> RiskAssessment:
        """Return the material risks derived from deterministic scoring inputs."""

        risks = [blocker.message for blocker in request.blockers]

        for component in request.breakdown.values():
            if component.status is ScoreStatus.MISSING:
                risks.extend(component.reasons)
            elif component.status is ScoreStatus.LIMITED and component.awarded_points == 0:
                risks.extend(component.reasons)

        deduped = _dedupe_messages(risks)
        confidence = 0.9 if request.blockers else (0.76 if deduped else 0.68)
        return RiskAssessment(
            risks=deduped,
            metadata=AITraceMetadata(
                provider_name="rule_based",
                provider_version="v1",
                generated_at=datetime.now(timezone.utc),
                confidence=confidence,
                debug_info={
                    "blocker_count": len(request.blockers),
                    "component_count": len(request.breakdown),
                    "risk_count": len(deduped),
                },
            ),
        )

    def collect_risks(self, payload: RiskScoringRequest) -> list[str]:
        """Compatibility wrapper that returns only the risk messages."""

        return self.score(payload).risks
