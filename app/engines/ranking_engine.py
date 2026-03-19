"""Field ranking engine built on top of the single-field suitability scorer.

Example:
```python
from app.engines.ranking_engine import rank_fields_for_crop

ranked = rank_fields_for_crop(
    fields=[field_a, field_b],
    crop_profile=crop,
    soil_tests={field_a.id: soil_a, field_b.id: soil_b},
    climate_summaries={field_a.id: climate_a, field_b.id: climate_b},
    top_n=3,
)

for candidate in ranked.ranked_fields:
    print(candidate.rank, candidate.field_name, candidate.total_score)
```
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.engines.scoring_types import ScoreBlocker, ScoreComponent, SuitabilityResult
from app.engines.suitability_engine import calculate_suitability
from app.models.crop_profile import CropProfile
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.schemas.weather_history import ClimateSummary
from app.services.crop_service import get_crop
from app.services.economic_service import EconomicAssessment, EconomicService
from app.services.field_service import get_field
from app.services.soil_service import get_latest_soil_test_for_field
from app.services.weather_service import WeatherService


SoilLookup = dict[int, SoilTest | None] | Callable[[Field], SoilTest | None]
ClimateLookup = dict[int, ClimateSummary | None] | Callable[[Field], ClimateSummary | None]
EconomicLookup = dict[int, EconomicAssessment | None] | Callable[[Field], EconomicAssessment | None]


@dataclass(slots=True)
class _FieldRankingCandidate:
    field_obj: Field
    scoring_result: SuitabilityResult
    economic_assessment: EconomicAssessment | None
    economic_score: float = 0.0
    ranking_score: float = 0.0


@dataclass(slots=True)
class RankedFieldResultInternal:
    """Detailed ranked candidate used inside the ranking engine."""

    rank: int
    field_id: int
    field_name: str
    crop_id: int
    total_score: float
    economic_score: float
    estimated_profit: float | None
    ranking_score: float
    breakdown: dict[str, ScoreComponent]
    blockers: list[ScoreBlocker]
    reasons: list[str]
    economic_strengths: list[str]
    economic_weaknesses: list[str]
    result: SuitabilityResult

    @property
    def score(self) -> float:
        """Compatibility alias for existing API adapter code."""

        return self.total_score


@dataclass(slots=True)
class RankingResult:
    """Ordered ranking output for a crop across multiple fields."""

    crop_id: int
    ranked_fields: list[RankedFieldResultInternal] = field(default_factory=list)

    def top(self, top_n: int | None) -> list[RankedFieldResultInternal]:
        """Return the top-N ranked entries or all when no limit is provided."""

        if top_n is None:
            return self.ranked_fields
        if top_n <= 0:
            return []
        return self.ranked_fields[:top_n]


def _resolve_soil_test(field_obj: Field, soil_tests: SoilLookup) -> SoilTest | None:
    if callable(soil_tests):
        return soil_tests(field_obj)
    return soil_tests.get(field_obj.id)


def _resolve_climate_summary(
    field_obj: Field,
    climate_summaries: ClimateLookup | None,
) -> ClimateSummary | None:
    if climate_summaries is None:
        return None
    if callable(climate_summaries):
        return climate_summaries(field_obj)
    return climate_summaries.get(field_obj.id)


def _resolve_economic_assessment(
    field_obj: Field,
    economic_assessments: EconomicLookup | None,
) -> EconomicAssessment | None:
    if economic_assessments is None:
        return None
    if callable(economic_assessments):
        return economic_assessments(field_obj)
    return economic_assessments.get(field_obj.id)


def _merge_reasons(*reason_sets: list[str]) -> list[str]:
    merged: list[str] = []
    for reason_set in reason_sets:
        for reason in reason_set:
            if reason not in merged:
                merged.append(reason)
    return merged


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


def _apply_economic_scoring(
    candidates: list[_FieldRankingCandidate],
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


def _ranked_result_from_score(
    rank: int,
    crop_profile: CropProfile,
    candidate: _FieldRankingCandidate,
) -> RankedFieldResultInternal:
    field_obj = candidate.field_obj
    scoring_result = candidate.scoring_result
    economic_assessment = candidate.economic_assessment
    return RankedFieldResultInternal(
        rank=rank,
        field_id=field_obj.id,
        field_name=field_obj.name,
        crop_id=crop_profile.id,
        total_score=scoring_result.total_score,
        economic_score=round(candidate.economic_score, 2),
        estimated_profit=(
            economic_assessment.estimated_profit
            if economic_assessment is not None
            else None
        ),
        ranking_score=round(candidate.ranking_score, 2),
        breakdown=scoring_result.score_breakdown,
        blockers=scoring_result.blockers,
        reasons=_merge_reasons(
            scoring_result.reasons,
            economic_assessment.reasons if economic_assessment is not None else [],
        ),
        economic_strengths=economic_assessment.strengths if economic_assessment is not None else [],
        economic_weaknesses=economic_assessment.weaknesses if economic_assessment is not None else [],
        result=scoring_result,
    )


def _score_field_candidates(
    fields: list[Field],
    crop_profile: CropProfile,
    soil_tests: SoilLookup,
    climate_summaries: ClimateLookup | None = None,
    economic_assessments: EconomicLookup | None = None,
) -> list[_FieldRankingCandidate]:
    scored_fields: list[_FieldRankingCandidate] = []
    for field_obj in fields:
        soil_test = _resolve_soil_test(field_obj, soil_tests)
        climate_summary = _resolve_climate_summary(field_obj, climate_summaries)
        economic_assessment = _resolve_economic_assessment(field_obj, economic_assessments)
        scoring_result = calculate_suitability(
            field_obj,
            crop_profile,
            soil_test,
            climate_summary=climate_summary,
        )
        scored_fields.append(
            _FieldRankingCandidate(
                field_obj=field_obj,
                scoring_result=scoring_result,
                economic_assessment=economic_assessment,
            )
        )
    return scored_fields


def rank_fields_for_crop(
    fields: list[Field],
    crop_profile: CropProfile,
    soil_tests: SoilLookup,
    top_n: int | None = None,
    climate_summaries: ClimateLookup | None = None,
    economic_assessments: EconomicLookup | None = None,
) -> RankingResult:
    """Rank multiple fields for a selected crop using the suitability engine."""

    scored_fields = _score_field_candidates(
        fields,
        crop_profile,
        soil_tests,
        climate_summaries=climate_summaries,
        economic_assessments=economic_assessments,
    )
    _apply_economic_scoring(scored_fields, economics_enabled=economic_assessments is not None)
    scored_fields.sort(key=lambda item: item.ranking_score, reverse=True)

    if top_n is not None and top_n <= 0:
        return RankingResult(crop_id=crop_profile.id, ranked_fields=[])

    if top_n is None:
        limited_fields = scored_fields
    else:
        limited_fields = scored_fields[:top_n]

    ranked_fields = [
        _ranked_result_from_score(index + 1, crop_profile, candidate)
        for index, candidate in enumerate(limited_fields)
    ]
    return RankingResult(crop_id=crop_profile.id, ranked_fields=ranked_fields)


def rank_fields(
    db: Session,
    field_ids: list[int],
    crop_id: int,
    top_n: int = 5,
) -> RankingResult:
    """DB-backed adapter that preserves the existing ranking API contract."""

    crop_profile = get_crop(db, crop_id)
    if not crop_profile:
        raise ValueError(f"Crop with id {crop_id} not found")

    fields: list[Field] = []
    for field_id in field_ids:
        field_obj = get_field(db, field_id)
        if field_obj is not None:
            fields.append(field_obj)

    soil_lookup = {
        field_obj.id: get_latest_soil_test_for_field(db, field_obj.id)
        for field_obj in fields
    }
    weather_service = WeatherService(db)
    climate_lookup = {
        field_obj.id: weather_service.get_climate_summary(field_obj.id)
        for field_obj in fields
    }
    economic_service = EconomicService(db)
    economic_lookup = {
        field_obj.id: economic_service.calculate_profit(
            field_obj,
            crop_profile,
            soil_test=soil_lookup[field_obj.id],
            climate_summary=climate_lookup[field_obj.id],
        )
        for field_obj in fields
    }
    return rank_fields_for_crop(
        fields,
        crop_profile,
        soil_lookup,
        top_n=top_n,
        climate_summaries=climate_lookup,
        economic_assessments=economic_lookup,
    )
