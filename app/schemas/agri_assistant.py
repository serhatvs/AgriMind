"""Schemas for LLM-assisted agronomic explanation and Q&A."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, PositiveInt

from app.schemas.ranking import CropSummary


class AgriAssistantAskRequest(BaseModel):
    """Request payload for field-ranking Q&A grounded in deterministic outputs."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1)
    crop_id: PositiveInt
    top_n: int | None = 5
    field_ids: list[PositiveInt] | None = None
    selected_field_id: PositiveInt | None = None


class AgriAssistantRankingRow(BaseModel):
    """Compact ranking row used in prompts and assistant context."""

    model_config = ConfigDict(extra="forbid")

    rank: int
    field_id: int
    field_name: str
    ranking_score: float
    total_score: float
    economic_score: float
    estimated_profit: float | None


class AgriAssistantContext(BaseModel):
    """Deterministic context derived from ranking and explanation outputs."""

    model_config = ConfigDict(extra="forbid")

    crop: CropSummary
    selected_field_id: int
    selected_field_name: str
    selected_field_rank: int
    selected_ranking_score: float
    selected_total_score: float
    why_this_field: list[str]
    alternatives: list[str]
    risks: list[str]
    missing_data: list[str]
    ranking_table: list[AgriAssistantRankingRow]


class AgriAssistantResponse(BaseModel):
    """Response returned by the agronomic assistant endpoint/service."""

    model_config = ConfigDict(extra="forbid")

    selected_field_id: int
    selected_field_name: str
    answer: str
    why_this_field: list[str]
    alternatives: list[str]
    risks: list[str]
    missing_data: list[str]
    used_fallback: bool
    model: str | None = None
