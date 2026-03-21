"""Reusable API-safe schemas for AI trace metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AITraceMetadataRead(BaseModel):
    """Serializable trace metadata returned with AI-adjacent outputs."""

    model_config = ConfigDict(extra="forbid")

    provider_name: str
    provider_version: str | None = None
    generated_at: datetime
    confidence: float | None = Field(default=None, ge=0, le=1)
    debug_info: dict[str, Any] | None = None
