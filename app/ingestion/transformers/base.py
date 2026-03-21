"""Transformer abstractions for converting raw payloads into normalized records."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.ingestion.types import NormalizedRecord, RawPayloadEnvelope
from app.models.ingestion import DataSource, IngestionRun


class PayloadTransformer(Protocol):
    """Protocol for components that transform raw payloads into normalized records."""

    def transform(
        self,
        payload: RawPayloadEnvelope,
        *,
        data_source: DataSource,
        ingestion_run: IngestionRun,
    ) -> Sequence[NormalizedRecord]:
        """Return normalized records derived from a raw payload."""
