"""Application service for ranking fields for a selected crop."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.engines.explanation_engine import build_ranked_field_explanation
from app.engines.ranking_engine import RankedFieldResultInternal, rank_fields_for_crop
from app.schemas.ranking import (
    CropSummary,
    RankFieldsResponse,
    RankedFieldRecommendation,
    ScoreBlockerRead,
    ScoreComponentRead,
)
from app.services.crop_service import get_crop
from app.services.field_service import get_all_fields, get_fields_by_ids
from app.services.soil_service import get_latest_soil_test_for_field


def _serialize_breakdown(breakdown: dict[str, object]) -> dict[str, ScoreComponentRead]:
    return {
        key: ScoreComponentRead.model_validate(component)
        for key, component in breakdown.items()
    }


def _serialize_blockers(blockers: list[object]) -> list[ScoreBlockerRead]:
    return [ScoreBlockerRead.model_validate(blocker) for blocker in blockers]


def _serialize_ranked_result(entry: RankedFieldResultInternal) -> RankedFieldRecommendation:
    return RankedFieldRecommendation(
        rank=entry.rank,
        field_id=entry.field_id,
        field_name=entry.field_name,
        total_score=entry.total_score,
        breakdown=_serialize_breakdown(entry.breakdown),
        blockers=_serialize_blockers(entry.blockers),
        reasons=entry.reasons,
        explanation=build_ranked_field_explanation(entry),
    )


def _load_fields_for_ranking(db: Session, field_ids: list[int] | None) -> list[object]:
    if field_ids is None:
        return get_all_fields(db)
    return get_fields_by_ids(db, field_ids)


def get_ranked_fields_response(
    db: Session,
    crop_id: int,
    top_n: int | None = 5,
    field_ids: list[int] | None = None,
) -> RankFieldsResponse:
    """Build the ranking response payload for the POST /rank-fields endpoint."""

    crop = get_crop(db, crop_id)
    if crop is None:
        raise ValueError(f"Crop with id {crop_id} not found")

    fields = _load_fields_for_ranking(db, field_ids)
    if not fields:
        if field_ids is None:
            raise ValueError("No fields found for ranking")
        raise ValueError("No fields found for the provided field filter")

    soil_lookup = {
        field.id: get_latest_soil_test_for_field(db, field.id)
        for field in fields
    }
    ranking = rank_fields_for_crop(fields, crop, soil_lookup, top_n=top_n)

    return RankFieldsResponse(
        crop=CropSummary.model_validate(crop),
        total_fields_evaluated=len(fields),
        ranked_results=[_serialize_ranked_result(entry) for entry in ranking.ranked_fields],
    )
