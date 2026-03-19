"""Schemas for yield prediction outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class YieldPredictionRange(BaseModel):
    """Confidence range around the predicted yield per hectare."""

    min: float = Field(..., ge=0)
    max: float = Field(..., ge=0)


class YieldPredictionResult(BaseModel):
    """Structured yield prediction result returned by the service layer."""

    model_config = ConfigDict(extra="forbid")

    field_id: int
    crop_id: int
    predicted_yield_per_hectare: float = Field(..., ge=0)
    predicted_yield_range: YieldPredictionRange
    confidence_score: float = Field(..., ge=0, le=1)
    model_version: str
    training_source: str
    feature_snapshot: dict[str, Any]
