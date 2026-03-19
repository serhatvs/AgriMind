"""Pydantic contracts for feedback-loop persistence services."""

from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator


class FeedbackWriteModel(BaseModel):
    """Common config for feedback write payloads."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class FeedbackReadModel(BaseModel):
    """Common config for feedback read payloads."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class RecommendationResultInput(FeedbackWriteModel):
    """Single ranked result captured in a recommendation run."""

    field_id: PositiveInt
    score: float = Field(..., ge=0, le=100)
    rank: PositiveInt


class RecommendationRunLog(FeedbackWriteModel):
    """Write payload for logging a recommendation run."""

    crop_id: PositiveInt
    results: list[RecommendationResultInput]

    @model_validator(mode="after")
    def validate_unique_results(self) -> "RecommendationRunLog":
        field_ids = [result.field_id for result in self.results]
        if len(field_ids) != len(set(field_ids)):
            raise ValueError("Recommendation results must not contain duplicate field_id values.")

        ranks = [result.rank for result in self.results]
        if len(ranks) != len(set(ranks)):
            raise ValueError("Recommendation results must not contain duplicate rank values.")
        return self


class UserDecisionLog(FeedbackWriteModel):
    """Write payload for logging the field selected by the user."""

    recommendation_run_id: PositiveInt
    selected_field_id: PositiveInt


class SeasonResultLog(FeedbackWriteModel):
    """Write payload for logging the final observed field outcome."""

    recommendation_run_id: PositiveInt
    field_id: PositiveInt
    crop_id: PositiveInt
    yield_amount: float = Field(
        ...,
        ge=0,
        validation_alias=AliasChoices("yield_amount", "yield"),
        serialization_alias="yield",
    )
    actual_cost: float = Field(..., ge=0)
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        if value == "":
            return None
        return value


class RecommendationResultRead(FeedbackReadModel):
    """Read schema for a single ranked recommendation."""

    recommendation_run_id: int
    field_id: int
    score: float
    rank: int


class UserDecisionRead(FeedbackReadModel):
    """Read schema for a recorded user selection."""

    recommendation_run_id: int
    selected_field_id: int


class SeasonResultRead(FeedbackReadModel):
    """Read schema for a logged season outcome."""

    recommendation_run_id: int
    field_id: int
    crop_id: int
    yield_amount: float = Field(
        ...,
        validation_alias=AliasChoices("yield_amount", "yield"),
        serialization_alias="yield",
    )
    actual_cost: float
    notes: str | None


class RecommendationRunRead(FeedbackReadModel):
    """Read schema for a complete closed-loop recommendation run."""

    id: int
    crop_id: int
    created_at: datetime
    results: list[RecommendationResultRead]
    user_decision: UserDecisionRead | None = None
    season_result: SeasonResultRead | None = None
