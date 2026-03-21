"""Runner that executes registered ingestion pipelines for configured data sources."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.ingestion.runners.registry import IngestionPipelineRegistry
from app.ingestion.services.pipeline import IngestionPipelineService
from app.ingestion.services.repository import IngestionRepository
from app.ingestion.types import IngestionExecutionResult
from app.models.enums import IngestionRunType


class IngestionJobRunner:
    """Execute ingestion pipelines for one or more configured data sources."""

    def __init__(
        self,
        db: Session,
        *,
        registry: IngestionPipelineRegistry,
        repository: IngestionRepository | None = None,
    ) -> None:
        self.db = db
        self.registry = registry
        self.repository = repository or IngestionRepository(db)

    def run_data_source(
        self,
        data_source_id: UUID,
        *,
        run_type: IngestionRunType = IngestionRunType.FULL,
    ) -> IngestionExecutionResult:
        """Execute the matching pipeline for a single data source."""

        data_source = self.repository.get_required_data_source(data_source_id)
        definition = self.registry.get(data_source.source_type)
        pipeline = IngestionPipelineService(
            self.db,
            client=definition.client,
            transformer=definition.transformer,
            writer=definition.writer,
            validators=definition.validators,
            repository=self.repository,
        )
        return pipeline.run(data_source.id, run_type=run_type)

    def run_active_sources(
        self,
        *,
        run_type: IngestionRunType = IngestionRunType.FULL,
    ) -> list[IngestionExecutionResult]:
        """Execute pipelines for every active data source."""

        return [
            self.run_data_source(data_source.id, run_type=run_type)
            for data_source in self.repository.list_active_data_sources()
        ]
