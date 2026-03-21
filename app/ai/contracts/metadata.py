"""Reusable trace metadata shared across AI-related provider outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class AITraceMetadata:
    """Trace metadata attached to AI-adjacent outputs for auditability."""

    provider_name: str
    provider_version: str | None
    generated_at: datetime
    confidence: float | None = None
    debug_info: dict[str, Any] | None = None

    def normalized(self) -> "AITraceMetadata":
        """Return a normalized metadata copy with UTC timestamps and clamped confidence."""

        generated_at = self.generated_at
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        else:
            generated_at = generated_at.astimezone(timezone.utc)

        confidence = self.confidence
        if confidence is not None:
            confidence = round(min(max(confidence, 0.0), 1.0), 2)

        return AITraceMetadata(
            provider_name=self.provider_name,
            provider_version=self.provider_version,
            generated_at=generated_at,
            confidence=confidence,
            debug_info=self.debug_info,
        )
