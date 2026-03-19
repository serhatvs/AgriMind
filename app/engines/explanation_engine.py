"""Deterministic explanation engine for ranked field suitability results.

Example:
```python
from app.engines.explanation_engine import build_ranked_field_explanation
from app.engines.ranking_engine import rank_fields_for_crop

ranked = rank_fields_for_crop(
    fields=[field_a, field_b],
    crop_profile=crop,
    soil_tests={field_a.id: soil_a, field_b.id: soil_b},
    top_n=2,
)

candidate = ranked.ranked_fields[0]
explanation = build_ranked_field_explanation(candidate)

print(explanation.short_explanation)
print(explanation.strengths)
print(explanation.risks)
```
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.engines.scoring_types import (
    ScoreBlocker,
    ScoreComponent,
    ScorePenalty,
    ScoreStatus,
    SuitabilityResult,
)
from app.models.crop_profile import CropProfile
from app.models.field import Field
from app.schemas.explanation import FieldExplanation


COMPONENT_ORDER = [
    "soil_compatibility",
    "ph_compatibility",
    "drainage_compatibility",
    "water_availability_compatibility",
    "slope_compatibility",
    "climate_compatibility",
]
COMPONENT_ORDER_INDEX = {key: index for index, key in enumerate(COMPONENT_ORDER)}


class _SupportsRankedExplanation(Protocol):
    field_name: str
    total_score: float
    ranking_score: float
    breakdown: dict[str, ScoreComponent]
    blockers: list[ScoreBlocker]
    reasons: list[str]
    economic_strengths: list[str]
    economic_weaknesses: list[str]
    result: SuitabilityResult


@dataclass(slots=True)
class _ExplanationContext:
    """Normalized explanation input shared by ranking and recommendation flows."""

    field_name: str
    display_score: float
    breakdown: dict[str, ScoreComponent]
    penalties: list[ScorePenalty]
    blockers: list[ScoreBlocker]
    reasons: list[str]
    economic_strengths: list[str]
    economic_weaknesses: list[str]


def _ordered_components(breakdown: dict[str, ScoreComponent]) -> list[tuple[str, ScoreComponent]]:
    seen: set[str] = set()
    ordered: list[tuple[str, ScoreComponent]] = []

    for key in COMPONENT_ORDER:
        if key in breakdown:
            ordered.append((key, breakdown[key]))
            seen.add(key)

    for key, component in breakdown.items():
        if key not in seen:
            ordered.append((key, component))

    return ordered


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


def _as_clause(message: str) -> str:
    clause = message.strip().rstrip(".")
    if not clause:
        return clause
    return clause[:1].lower() + clause[1:]


def _join_clauses(messages: list[str]) -> str:
    clauses = [_as_clause(message) for message in messages if message.strip()]
    if not clauses:
        return ""
    if len(clauses) == 1:
        return clauses[0]
    if len(clauses) == 2:
        return f"{clauses[0]} and {clauses[1]}"
    return f"{', '.join(clauses[:-1])}, and {clauses[-1]}"


def _as_sentence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    if stripped.endswith((".", "!", "?")):
        return stripped
    return f"{stripped}."


def _suitability_label(total_score: float, blockers: list[ScoreBlocker]) -> str:
    if blockers or total_score < 40:
        return "not suitable"
    if total_score >= 80:
        return "highly suitable"
    if total_score >= 60:
        return "moderately suitable"
    return "marginally suitable"


def _collect_strengths(
    breakdown: dict[str, ScoreComponent],
    economic_strengths: list[str],
) -> list[str]:
    strengths: list[str] = []
    for _, component in _ordered_components(breakdown):
        if component.status is ScoreStatus.IDEAL:
            strengths.extend(component.reasons)
    strengths.extend(economic_strengths)
    return _dedupe_messages(strengths)


def _collect_weaknesses(
    penalties: list[ScorePenalty],
    economic_weaknesses: list[str],
) -> list[str]:
    ordered_penalties = sorted(
        penalties,
        key=lambda penalty: (
            -penalty.points_lost,
            COMPONENT_ORDER_INDEX.get(penalty.dimension, len(COMPONENT_ORDER_INDEX)),
        ),
    )
    weaknesses = [penalty.message for penalty in ordered_penalties]
    weaknesses.extend(economic_weaknesses)
    return _dedupe_messages(weaknesses)


def _collect_risks(
    breakdown: dict[str, ScoreComponent],
    blockers: list[ScoreBlocker],
) -> list[str]:
    risks = [blocker.message for blocker in blockers]

    for _, component in _ordered_components(breakdown):
        if component.status is ScoreStatus.MISSING:
            risks.extend(component.reasons)
        elif component.status is ScoreStatus.LIMITED and component.awarded_points == 0:
            risks.extend(component.reasons)

    return _dedupe_messages(risks)


def _collect_additional_reasons(
    reasons: list[str],
    strengths: list[str],
    weaknesses: list[str],
    risks: list[str],
) -> list[str]:
    used = set(strengths + weaknesses + risks)
    return [reason for reason in _dedupe_messages(reasons) if reason not in used]


def _build_short_explanation(
    display_score: float,
    strengths: list[str],
    weaknesses: list[str],
    risks: list[str],
    reasons: list[str],
    blockers: list[ScoreBlocker],
) -> str:
    label = _suitability_label(display_score, blockers)

    if blockers and risks:
        return _as_sentence(
            f"This field is {label} because {_join_clauses(risks[:2])}"
        )

    if display_score >= 80 and strengths:
        return _as_sentence(
            f"This field ranked highly because {_join_clauses(strengths[:2])}"
        )

    if display_score >= 60 and strengths:
        return _as_sentence(
            f"This field is {label} because {_join_clauses(strengths[:2])}"
        )

    if weaknesses:
        return _as_sentence(
            f"This field lost points because {_join_clauses(weaknesses[:2])}"
        )

    if risks:
        return _as_sentence(
            f"This field faces material risks because {_join_clauses(risks[:2])}"
        )

    if reasons:
        return _as_sentence(
            f"This field is {label} based on the current scoring results"
        )

    return _as_sentence(f"This field is {label}")


def _build_detailed_explanation(
    field_name: str,
    display_score: float,
    strengths: list[str],
    weaknesses: list[str],
    risks: list[str],
    additional_reasons: list[str],
    blockers: list[ScoreBlocker],
) -> str:
    label = _suitability_label(display_score, blockers)
    sentences = [
        _as_sentence(
            f"Field '{field_name}' is {label} based on the current scoring results (score: {display_score:.1f}/100)"
        )
    ]

    if blockers:
        blocker_messages = _dedupe_messages([blocker.message for blocker in blockers])
        sentences.append(_as_sentence("Blockers: " + "; ".join(blocker_messages[:3])))
    elif strengths:
        sentences.append(_as_sentence("Strengths: " + "; ".join(strengths[:3])))

    if weaknesses:
        sentences.append(_as_sentence("Weaknesses: " + "; ".join(weaknesses[:3])))

    if blockers and strengths:
        sentences.append(_as_sentence("Strengths: " + "; ".join(strengths[:3])))
    elif not blockers and risks:
        sentences.append(_as_sentence("Risks: " + "; ".join(risks[:3])))
    elif not blockers and not weaknesses and additional_reasons:
        sentences.append(_as_sentence("Additional factors: " + "; ".join(additional_reasons[:3])))
    elif not blockers and not risks:
        sentences.append("No significant risks were identified from the current scoring inputs.")

    return " ".join(sentence for sentence in sentences[:4] if sentence)


def _build_explanation(context: _ExplanationContext) -> FieldExplanation:
    strengths = _collect_strengths(context.breakdown, context.economic_strengths)
    weaknesses = _collect_weaknesses(context.penalties, context.economic_weaknesses)
    risks = _collect_risks(context.breakdown, context.blockers)
    additional_reasons = _collect_additional_reasons(
        context.reasons,
        strengths,
        weaknesses,
        risks,
    )

    return FieldExplanation(
        short_explanation=_build_short_explanation(
            context.display_score,
            strengths,
            weaknesses,
            risks,
            context.reasons,
            context.blockers,
        ),
        detailed_explanation=_build_detailed_explanation(
            context.field_name,
            context.display_score,
            strengths,
            weaknesses,
            risks,
            additional_reasons,
            context.blockers,
        ),
        strengths=strengths,
        weaknesses=weaknesses,
        risks=risks,
    )


def build_ranked_field_explanation(ranked_result: _SupportsRankedExplanation) -> FieldExplanation:
    """Build a structured explanation from a ranked field result."""

    context = _ExplanationContext(
        field_name=ranked_result.field_name,
        display_score=getattr(ranked_result, "ranking_score", ranked_result.total_score),
        breakdown=ranked_result.breakdown,
        penalties=ranked_result.result.penalties,
        blockers=ranked_result.blockers,
        reasons=ranked_result.reasons,
        economic_strengths=getattr(ranked_result, "economic_strengths", []),
        economic_weaknesses=getattr(ranked_result, "economic_weaknesses", []),
    )
    return _build_explanation(context)


def build_suitability_explanation(
    result: SuitabilityResult,
    field_obj: Field,
    rank: int = 1,
) -> FieldExplanation:
    """Build a structured explanation from a single-field suitability result."""

    _ = rank
    context = _ExplanationContext(
        field_name=field_obj.name,
        display_score=result.total_score,
        breakdown=result.score_breakdown,
        penalties=result.penalties,
        blockers=result.blockers,
        reasons=result.reasons,
        economic_strengths=[],
        economic_weaknesses=[],
    )
    return _build_explanation(context)


def generate_explanation(
    result: SuitabilityResult,
    field_obj: Field,
    crop: CropProfile,
) -> str:
    """Return the legacy explanation string used by existing API responses."""

    _ = crop
    explanation = build_suitability_explanation(result, field_obj)
    return explanation.detailed_explanation
