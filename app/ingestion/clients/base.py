"""Client abstractions for fetching raw ingestion payloads."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.ingestion.types import RawPayloadEnvelope
from app.models.enums import IngestionRunType
from app.models.ingestion import DataSource


class IngestionClient(Protocol):
    """Protocol for components that fetch raw payloads from an upstream source."""

    def fetch(
        self,
        data_source: DataSource,
        *,
        run_type: IngestionRunType,
    ) -> Sequence[RawPayloadEnvelope]:
        """Fetch one or more raw payload envelopes for the configured source."""
