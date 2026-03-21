"""Registry for mapping configured data sources to source-specific ingestion runners."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from app.ingestion.services.repository import IngestionRepository
from app.ingestion.types import IngestionExecutionResult
from app.models.enums import DataSourceType, IngestionRunType
from app.models.ingestion import DataSource


class SourceIngestionExecutor(Protocol):
    """Protocol for source-specific ingestion executor functions."""

    def __call__(
        self,
        db: Session,
        *,
        run_type: IngestionRunType,
        repository: IngestionRepository,
        data_source: DataSource,
    ) -> IngestionExecutionResult:
        """Execute a source-specific ingestion job for a registered data source."""


@dataclass(frozen=True, slots=True)
class IngestionSourceDefinition:
    """Registration record describing how a configured source should be executed."""

    source_name: str
    source_type: DataSourceType
    base_url: str | None
    executor: SourceIngestionExecutor
    aliases: tuple[str, ...] = ()
    default_is_active: bool = True

    def matches(self, source_name: str) -> bool:
        """Return whether the provided source name matches this definition."""

        normalized_name = normalize_source_name(source_name)
        return normalized_name in {
            normalize_source_name(self.source_name),
            *(normalize_source_name(alias) for alias in self.aliases),
        }

    def ensure_data_source(self, repository: IngestionRepository) -> DataSource:
        """Ensure the backing data source row exists in the database."""

        return repository.ensure_registered_data_source(
            source_name=self.source_name,
            source_type=self.source_type,
            base_url=self.base_url,
            default_is_active=self.default_is_active,
        )


class IngestionSourceRunnerRegistry:
    """Store source-specific ingestion executors keyed by source-name aliases."""

    def __init__(self) -> None:
        self._definitions: list[IngestionSourceDefinition] = []
        self._name_map: dict[str, IngestionSourceDefinition] = {}

    def register(self, definition: IngestionSourceDefinition) -> None:
        """Register a source definition for unified orchestration."""

        normalized_names = {
            normalize_source_name(definition.source_name),
            *(normalize_source_name(alias) for alias in definition.aliases),
        }
        for normalized_name in normalized_names:
            existing_definition = self._name_map.get(normalized_name)
            if existing_definition is not None and existing_definition is not definition:
                raise ValueError(f"Duplicate ingestion source registration for '{normalized_name}'")

        self._definitions.append(definition)
        for normalized_name in normalized_names:
            self._name_map[normalized_name] = definition

    def get(self, source_name: str) -> IngestionSourceDefinition:
        """Return the matching source definition for a configured data source name."""

        try:
            return self._name_map[normalize_source_name(source_name)]
        except KeyError as exc:
            raise KeyError(f"No ingestion source runner registered for '{source_name}'") from exc

    def definitions(self) -> tuple[IngestionSourceDefinition, ...]:
        """Return the registered source definitions in registration order."""

        return tuple(self._definitions)

    def ensure_registered_sources(self, repository: IngestionRepository) -> list[DataSource]:
        """Ensure every registered source has a backing data_sources row."""

        return [definition.ensure_data_source(repository) for definition in self._definitions]


def normalize_source_name(source_name: str) -> str:
    """Normalize a source name for case-insensitive registry lookup."""

    return source_name.strip().casefold()


def build_default_source_runner_registry() -> IngestionSourceRunnerRegistry:
    """Return the default registry containing every built-in ingestion source."""

    from app.ingestion.runners.run_faostat import build_faostat_source_definition
    from app.ingestion.runners.run_nasa_power import build_nasa_power_source_definition

    registry = IngestionSourceRunnerRegistry()
    registry.register(build_nasa_power_source_definition())
    registry.register(build_faostat_source_definition())
    return registry
