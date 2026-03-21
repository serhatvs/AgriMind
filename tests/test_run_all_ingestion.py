from __future__ import annotations

from uuid import UUID, uuid4

from app.ingestion.runners.run_all import SKIPPED_SOURCE_STATUS, execute_all_ingestions
from app.ingestion.runners.source_registry import IngestionSourceDefinition, IngestionSourceRunnerRegistry
from app.ingestion.services import IngestionRepository
from app.ingestion.types import IngestionExecutionResult
from app.models.enums import DataSourceType, IngestionRunStatus, IngestionRunType
from app.models.ingestion import DataSource


class _Executor:
    def __init__(self, result: IngestionExecutionResult | None = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, object]] = []

    def __call__(self, db, *, run_type, repository, data_source):
        self.calls.append(
            {
                "db": db,
                "run_type": run_type,
                "repository": repository,
                "data_source": data_source,
            }
        )
        if self.error is not None:
            raise self.error
        return self.result


def _build_result(
    *,
    ingestion_run_id: int,
    data_source_id: UUID,
    status: IngestionRunStatus,
    fetched: int,
    inserted: int,
    skipped: int,
) -> IngestionExecutionResult:
    return IngestionExecutionResult(
        ingestion_run_id=ingestion_run_id,
        data_source_id=data_source_id,
        status=status,
        records_fetched=fetched,
        records_inserted=inserted,
        records_skipped=skipped,
        error_message=None,
        metadata_json={},
    )


def test_source_registry_ensures_data_sources_without_reenabling_disabled_rows(db):
    repository = IngestionRepository(db)
    existing_source = DataSource(
        source_name="NASA POWER Daily",
        source_type=DataSourceType.API,
        base_url="https://old.example.test",
        is_active=False,
    )
    db.add(existing_source)
    db.commit()

    registry = IngestionSourceRunnerRegistry()
    registry.register(
        IngestionSourceDefinition(
            source_name="NASA POWER Daily",
            source_type=DataSourceType.API,
            base_url="https://new.example.test",
            executor=_Executor(
                _build_result(
                    ingestion_run_id=1,
                    data_source_id=uuid4(),
                    status=IngestionRunStatus.SUCCEEDED,
                    fetched=0,
                    inserted=0,
                    skipped=0,
                )
            ),
        )
    )

    ensured_sources = registry.ensure_registered_sources(repository)

    assert len(ensured_sources) == 1
    assert ensured_sources[0].id == existing_source.id
    assert ensured_sources[0].base_url == "https://new.example.test"
    assert ensured_sources[0].is_active is False


def test_source_registry_skips_disabled_definitions_when_ensuring_sources(db):
    repository = IngestionRepository(db)
    registry = IngestionSourceRunnerRegistry()
    registry.register(
        IngestionSourceDefinition(
            source_name="NASA POWER Daily",
            source_type=DataSourceType.API,
            base_url="https://power.example.test",
            executor=_Executor(
                _build_result(
                    ingestion_run_id=1,
                    data_source_id=uuid4(),
                    status=IngestionRunStatus.SUCCEEDED,
                    fetched=0,
                    inserted=0,
                    skipped=0,
                )
            ),
            is_enabled=False,
        )
    )
    registry.register(
        IngestionSourceDefinition(
            source_name="FAOSTAT Crops and Livestock",
            source_type=DataSourceType.API,
            base_url="https://faostat.example.test",
            executor=_Executor(
                _build_result(
                    ingestion_run_id=2,
                    data_source_id=uuid4(),
                    status=IngestionRunStatus.SUCCEEDED,
                    fetched=0,
                    inserted=0,
                    skipped=0,
                )
            ),
        )
    )

    ensured_sources = registry.ensure_registered_sources(repository)

    assert [source.source_name for source in ensured_sources] == ["FAOSTAT Crops and Livestock"]
    assert repository.get_data_source_by_name("NASA POWER Daily") is None


def test_execute_all_ingestions_runs_active_sources_and_aggregates_summary(db):
    repository = IngestionRepository(db)

    success_executor = _Executor(
        _build_result(
            ingestion_run_id=1,
            data_source_id=uuid4(),
            status=IngestionRunStatus.SUCCEEDED,
            fetched=5,
            inserted=4,
            skipped=1,
        )
    )
    partial_executor = _Executor(
        _build_result(
            ingestion_run_id=2,
            data_source_id=uuid4(),
            status=IngestionRunStatus.PARTIAL,
            fetched=3,
            inserted=2,
            skipped=1,
        )
    )

    registry = IngestionSourceRunnerRegistry()
    registry.register(
        IngestionSourceDefinition(
            source_name="NASA POWER Daily",
            source_type=DataSourceType.API,
            base_url="https://power.example.test",
            executor=success_executor,
        )
    )
    registry.register(
        IngestionSourceDefinition(
            source_name="FAOSTAT Crops and Livestock",
            source_type=DataSourceType.API,
            base_url="https://faostat.example.test",
            executor=partial_executor,
        )
    )
    registry.ensure_registered_sources(repository)

    db.add(
        DataSource(
            source_name="Unsupported Source",
            source_type=DataSourceType.API,
            base_url="https://unsupported.example.test",
            is_active=True,
        )
    )
    db.commit()

    summary = execute_all_ingestions(
        db,
        run_type=IngestionRunType.BACKFILL,
        repository=repository,
        registry=registry,
        ensure_registered_sources=False,
    )

    assert summary.total_sources == 3
    assert summary.succeeded_sources == 1
    assert summary.partial_sources == 1
    assert summary.failed_sources == 1
    assert summary.skipped_sources == 0
    assert {report.source_name: report.status for report in summary.reports} == {
        "FAOSTAT Crops and Livestock": "partial",
        "NASA POWER Daily": "succeeded",
        "Unsupported Source": "failed",
    }
    assert success_executor.calls[0]["run_type"] == IngestionRunType.BACKFILL
    assert partial_executor.calls[0]["run_type"] == IngestionRunType.BACKFILL
    assert "No ingestion source runner registered" in (summary.reports[2].error_message or "")


def test_execute_all_ingestions_skips_active_sources_disabled_by_config(db):
    repository = IngestionRepository(db)
    success_executor = _Executor(
        _build_result(
            ingestion_run_id=1,
            data_source_id=uuid4(),
            status=IngestionRunStatus.SUCCEEDED,
            fetched=2,
            inserted=2,
            skipped=0,
        )
    )
    disabled_executor = _Executor(
        _build_result(
            ingestion_run_id=2,
            data_source_id=uuid4(),
            status=IngestionRunStatus.SUCCEEDED,
            fetched=1,
            inserted=1,
            skipped=0,
        )
    )

    registry = IngestionSourceRunnerRegistry()
    registry.register(
        IngestionSourceDefinition(
            source_name="NASA POWER Daily",
            source_type=DataSourceType.API,
            base_url="https://power.example.test",
            executor=disabled_executor,
            is_enabled=False,
        )
    )
    registry.register(
        IngestionSourceDefinition(
            source_name="FAOSTAT Crops and Livestock",
            source_type=DataSourceType.API,
            base_url="https://faostat.example.test",
            executor=success_executor,
        )
    )

    db.add_all(
        [
            DataSource(
                source_name="NASA POWER Daily",
                source_type=DataSourceType.API,
                base_url="https://power.example.test",
                is_active=True,
            ),
            DataSource(
                source_name="FAOSTAT Crops and Livestock",
                source_type=DataSourceType.API,
                base_url="https://faostat.example.test",
                is_active=True,
            ),
        ]
    )
    db.commit()

    summary = execute_all_ingestions(
        db,
        run_type=IngestionRunType.INCREMENTAL,
        repository=repository,
        registry=registry,
        ensure_registered_sources=False,
    )

    assert summary.total_sources == 2
    assert summary.succeeded_sources == 1
    assert summary.partial_sources == 0
    assert summary.failed_sources == 0
    assert summary.skipped_sources == 1
    assert {report.source_name: report.status for report in summary.reports} == {
        "FAOSTAT Crops and Livestock": "succeeded",
        "NASA POWER Daily": SKIPPED_SOURCE_STATUS,
    }
    assert len(disabled_executor.calls) == 0
    assert len(success_executor.calls) == 1
