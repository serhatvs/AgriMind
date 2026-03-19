"""Schemas for the field ranking API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, PositiveInt

from app.engines.scoring_types import ScoreStatus
from app.schemas.explanation import FieldExplanation


class RankFieldsRequest(BaseModel):
    """Request payload for ranking fields against a selected crop."""

    model_config = ConfigDict(extra="forbid")

    crop_id: PositiveInt
    top_n: int | None = 5
    field_ids: list[PositiveInt] | None = None


class CropSummary(BaseModel):
    """Compact crop profile summary returned alongside ranking results."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    crop_name: str
    scientific_name: str | None


class ScoreComponentRead(BaseModel):
    """Serialized scoring component included in ranking responses."""

    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    weight: float
    awarded_points: float
    max_points: float
    status: ScoreStatus
    reasons: list[str]


class ScoreBlockerRead(BaseModel):
    """Serialized hard blocker included in ranking responses."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    dimension: str
    message: str


class RankedFieldRecommendation(BaseModel):
    """Single ranked recommendation entry for a field."""

    rank: int
    field_id: int
    field_name: str
    total_score: float
    economic_score: float
    estimated_profit: float | None
    ranking_score: float
    breakdown: dict[str, ScoreComponentRead]
    blockers: list[ScoreBlockerRead]
    reasons: list[str]
    explanation: FieldExplanation


class RankFieldsResponse(BaseModel):
    """Response payload returned by the field ranking endpoint."""

    crop: CropSummary
    total_fields_evaluated: int
    ranked_results: list[RankedFieldRecommendation]
