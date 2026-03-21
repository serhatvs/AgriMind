"""Registry for mapping source types to ingestion pipeline components."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ingestion.clients.base import IngestionClient
from app.ingestion.errors import UnsupportedDataSourceTypeError
from app.ingestion.services.pipeline import NormalizedRecordWriter
from app.ingestion.transformers.base import PayloadTransformer
from app.ingestion.validators.base import RecordValidator
from app.models.enums import DataSourceType


@dataclass(frozen=True, slots=True)
class IngestionPipelineDefinition:
    """Concrete pipeline components bound to a source type."""

    client: IngestionClient
    transformer: PayloadTransformer
    writer: NormalizedRecordWriter
    validators: tuple[RecordValidator, ...] = field(default_factory=tuple)


class IngestionPipelineRegistry:
    """Store reusable ingestion pipeline definitions keyed by source type."""

    def __init__(self) -> None:
        self._definitions: dict[str, IngestionPipelineDefinition] = {}

    def register(
        self,
        source_type: DataSourceType | str,
        definition: IngestionPipelineDefinition,
    ) -> None:
        """Register a pipeline definition for a source type."""

        normalized_key = self._normalize_source_type(source_type)
        self._definitions[normalized_key] = definition

    def get(self, source_type: DataSourceType | str) -> IngestionPipelineDefinition:
        """Return the pipeline definition for the source type or raise."""

        normalized_key = self._normalize_source_type(source_type)
        try:
            return self._definitions[normalized_key]
        except KeyError as exc:
            raise UnsupportedDataSourceTypeError(
                f"No ingestion pipeline registered for source type '{normalized_key}'"
            ) from exc

    @staticmethod
    def _normalize_source_type(source_type: DataSourceType | str) -> str:
        if isinstance(source_type, DataSourceType):
            return source_type.value
        return source_type.strip().lower()
