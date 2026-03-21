"""Schemas for yield prediction outputs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.ai_metadata import AITraceMetadataRead


class YieldPredictionRange(BaseModel):
    """Confidence range around the predicted yield per hectare."""

    min: float = Field(..., ge=0)
    max: float = Field(..., ge=0)


class YieldPredictionResult(BaseModel):
    """Structured yield prediction result returned by the service layer."""

    model_config = ConfigDict(extra="forbid")

    field_id: int | str | UUID
    crop_id: int | str | UUID
    predicted_yield_per_hectare: float = Field(..., ge=0)
    predicted_yield_min: float = Field(..., ge=0)
    predicted_yield_max: float = Field(..., ge=0)
    predicted_yield_range: YieldPredictionRange
    confidence_score: float = Field(..., ge=0, le=1)
    model_version: str
    training_source: str
    feature_snapshot: dict[str, Any]
    metadata: AITraceMetadataRead

    @model_validator(mode="before")
    @classmethod
    def hydrate_range_bounds(cls, data: Any) -> Any:
        """Backfill explicit range fields from the legacy range payload when needed."""

        if not isinstance(data, dict):
            return data

        range_payload = data.get("predicted_yield_range")
        if data.get("predicted_yield_min") is None and isinstance(range_payload, dict):
            data["predicted_yield_min"] = range_payload.get("min")
        if data.get("predicted_yield_max") is None and isinstance(range_payload, dict):
            data["predicted_yield_max"] = range_payload.get("max")
        return data
