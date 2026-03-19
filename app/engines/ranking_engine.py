"""Field ranking engine built on top of the single-field suitability scorer.

Example:
```python
from app.engines.ranking_engine import rank_fields_for_crop

ranked = rank_fields_for_crop(
    fields=[field_a, field_b],
    crop_profile=crop,
    soil_tests={field_a.id: soil_a, field_b.id: soil_b},
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
from app.services.crop_service import get_crop
from app.services.field_service import get_field
from app.services.soil_service import get_latest_soil_test_for_field


SoilLookup = dict[int, SoilTest | None] | Callable[[Field], SoilTest | None]


@dataclass(slots=True)
class RankedFieldResultInternal:
    """Detailed ranked candidate used inside the ranking engine."""

    rank: int
    field_id: int
    field_name: str
    crop_id: int
    total_score: float
    breakdown: dict[str, ScoreComponent]
    blockers: list[ScoreBlocker]
    reasons: list[str]
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


def _ranked_result_from_score(
    rank: int,
    field_obj: Field,
    crop_profile: CropProfile,
    scoring_result: SuitabilityResult,
) -> RankedFieldResultInternal:
    return RankedFieldResultInternal(
        rank=rank,
        field_id=field_obj.id,
        field_name=field_obj.name,
        crop_id=crop_profile.id,
        total_score=scoring_result.total_score,
        breakdown=scoring_result.score_breakdown,
        blockers=scoring_result.blockers,
        reasons=scoring_result.reasons,
        result=scoring_result,
    )


def _score_field_candidates(
    fields: list[Field],
    crop_profile: CropProfile,
    soil_tests: SoilLookup,
) -> list[tuple[Field, SuitabilityResult]]:
    scored_fields: list[tuple[Field, SuitabilityResult]] = []
    for field_obj in fields:
        soil_test = _resolve_soil_test(field_obj, soil_tests)
        scoring_result = calculate_suitability(field_obj, crop_profile, soil_test)
        scored_fields.append((field_obj, scoring_result))
    return scored_fields


def rank_fields_for_crop(
    fields: list[Field],
    crop_profile: CropProfile,
    soil_tests: SoilLookup,
    top_n: int | None = None,
) -> RankingResult:
    """Rank multiple fields for a selected crop using the suitability engine."""

    scored_fields = _score_field_candidates(fields, crop_profile, soil_tests)
    scored_fields.sort(key=lambda item: item[1].total_score, reverse=True)

    if top_n is not None and top_n <= 0:
        return RankingResult(crop_id=crop_profile.id, ranked_fields=[])

    if top_n is None:
        limited_fields = scored_fields
    else:
        limited_fields = scored_fields[:top_n]

    ranked_fields = [
        _ranked_result_from_score(index + 1, field_obj, crop_profile, scoring_result)
        for index, (field_obj, scoring_result) in enumerate(limited_fields)
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
    return rank_fields_for_crop(fields, crop_profile, soil_lookup, top_n=top_n)
