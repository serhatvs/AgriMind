"""Persistence services for recommendation feedback loops.

Example:
```python
from app.schemas.feedback import (
    RecommendationResultInput,
    RecommendationRunLog,
    SeasonResultLog,
    UserDecisionLog,
)
from app.services.feedback_service import (
    log_recommendation,
    log_season_result,
    log_user_decision,
)
from app.services.ranking_service import get_ranked_fields_response

ranking = get_ranked_fields_response(db, crop_id=1, field_ids=[1, 2, 3], top_n=3)

run = log_recommendation(
    db,
    RecommendationRunLog(
        crop_id=ranking.crop.id,
        results=[
            RecommendationResultInput(
                field_id=item.field_id,
                score=item.ranking_score,
                rank=item.rank,
            )
            for item in ranking.ranked_results
        ],
    ),
)

log_user_decision(
    db,
    UserDecisionLog(
        recommendation_run_id=run.id,
        selected_field_id=run.results[0].field_id,
    ),
)

log_season_result(
    db,
    SeasonResultLog.model_validate(
        {
            "recommendation_run_id": run.id,
            "field_id": run.results[0].field_id,
            "crop_id": ranking.crop.id,
            "yield": 8.4,
            "actual_cost": 1320.0,
            "notes": "Observed after harvest.",
        }
    ),
)
```
"""

from __future__ import annotations

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models.feedback import RecommendationResult, RecommendationRun, SeasonResult, UserDecision
from app.schemas.feedback import RecommendationRunLog, SeasonResultLog, UserDecisionLog
from app.services.crop_service import get_crop
from app.services.field_service import get_field, get_fields_by_ids


def _commit(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def _load_recommendation_run(db: Session, recommendation_run_id: int) -> RecommendationRun | None:
    return (
        db.query(RecommendationRun)
        .options(
            selectinload(RecommendationRun.results),
            selectinload(RecommendationRun.user_decision),
            selectinload(RecommendationRun.season_result),
        )
        .filter(RecommendationRun.id == recommendation_run_id)
        .first()
    )


def _validate_result_fields_exist(db: Session, field_ids: list[int]) -> None:
    unique_ids = list(dict.fromkeys(field_ids))
    existing_fields = get_fields_by_ids(db, unique_ids)
    existing_ids = {field.id for field in existing_fields}
    missing_ids = [field_id for field_id in unique_ids if field_id not in existing_ids]
    if missing_ids:
        missing_display = ", ".join(str(field_id) for field_id in missing_ids)
        raise ValueError(f"Field not found for ids: {missing_display}")


def log_recommendation(db: Session, payload: RecommendationRunLog) -> RecommendationRun:
    """Persist a recommendation run and all ranked results in one transaction."""

    crop = get_crop(db, payload.crop_id)
    if crop is None:
        raise ValueError(f"Crop with id {payload.crop_id} not found")

    _validate_result_fields_exist(db, [result.field_id for result in payload.results])

    recommendation_run = RecommendationRun(
        crop_id=payload.crop_id,
        results=[
            RecommendationResult(
                field_id=result.field_id,
                score=result.score,
                rank=result.rank,
            )
            for result in payload.results
        ],
    )
    db.add(recommendation_run)
    _commit(db)
    return _load_recommendation_run(db, recommendation_run.id) or recommendation_run


def log_user_decision(db: Session, payload: UserDecisionLog) -> UserDecision:
    """Persist the field selected by the user for a recommendation run."""

    recommendation_run = db.get(RecommendationRun, payload.recommendation_run_id)
    if recommendation_run is None:
        raise ValueError(f"Recommendation run with id {payload.recommendation_run_id} not found")

    selected_field = get_field(db, payload.selected_field_id)
    if selected_field is None:
        raise ValueError(f"Field with id {payload.selected_field_id} not found")

    existing_decision = db.get(UserDecision, payload.recommendation_run_id)
    if existing_decision is not None:
        raise ValueError(f"User decision already exists for recommendation run {payload.recommendation_run_id}")

    decision = UserDecision(
        recommendation_run_id=payload.recommendation_run_id,
        selected_field_id=payload.selected_field_id,
    )
    db.add(decision)
    _commit(db)
    db.refresh(decision)
    return decision


def log_season_result(db: Session, payload: SeasonResultLog) -> SeasonResult:
    """Persist the observed outcome for the field selected in a recommendation run."""

    recommendation_run = db.get(RecommendationRun, payload.recommendation_run_id)
    if recommendation_run is None:
        raise ValueError(f"Recommendation run with id {payload.recommendation_run_id} not found")

    field_obj = get_field(db, payload.field_id)
    if field_obj is None:
        raise ValueError(f"Field with id {payload.field_id} not found")

    crop = get_crop(db, payload.crop_id)
    if crop is None:
        raise ValueError(f"Crop with id {payload.crop_id} not found")

    if payload.crop_id != recommendation_run.crop_id:
        raise ValueError("Season result crop_id must match the crop_id recorded on the recommendation run.")

    existing_result = db.get(SeasonResult, payload.recommendation_run_id)
    if existing_result is not None:
        raise ValueError(f"Season result already exists for recommendation run {payload.recommendation_run_id}")

    user_decision = db.get(UserDecision, payload.recommendation_run_id)
    if user_decision is None:
        raise ValueError("A user decision must be logged before the season result can be recorded.")

    if payload.field_id != user_decision.selected_field_id:
        raise ValueError("Season result field_id must match the field selected in the user decision.")

    season_result = SeasonResult(
        recommendation_run_id=payload.recommendation_run_id,
        field_id=payload.field_id,
        crop_id=payload.crop_id,
        yield_amount=payload.yield_amount,
        actual_cost=payload.actual_cost,
        notes=payload.notes,
    )
    db.add(season_result)
    _commit(db)
    db.refresh(season_result)
    return season_result
