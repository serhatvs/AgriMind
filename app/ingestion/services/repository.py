"""Persistence helpers for ingestion configuration and execution records."""

from __future__ import annotations

from datetime import datetime
import logging
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.reflection import tables_exist
from app.ingestion.types import RawPayloadEnvelope
from app.models.enums import DataSourceType, IngestionPayloadType, IngestionRunStatus, IngestionRunType
from app.models.ingestion import DataSource, IngestionRun, RawIngestionPayload
from app.models.mixins import utc_now
from app.services.errors import NotFoundError, ServiceValidationError


logger = logging.getLogger(__name__)


class IngestionRepository:
    """Repository wrapper around the ingestion ORM models."""

    REQUIRED_TABLES = ("data_sources", "ingestion_runs", "raw_ingestion_payloads")

    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_ingestion_tables_ready(self) -> None:
        """Fail fast when the ingestion infrastructure tables are unavailable."""

        if not tables_exist(self.db, *self.REQUIRED_TABLES):
            if settings.INGESTION_AUTO_CREATE_TABLES:
                self._create_ingestion_tables()
            if not tables_exist(self.db, *self.REQUIRED_TABLES):
                required = ", ".join(self.REQUIRED_TABLES)
                raise ServiceValidationError(
                    f"Ingestion tables are missing ({required}). Run 'alembic upgrade head' before starting ingestion."
                )

    def _create_ingestion_tables(self) -> None:
        """Create only the ingestion infrastructure tables when they are missing."""

        bind = self.db.get_bind()
        if bind is None:
            required = ", ".join(self.REQUIRED_TABLES)
            raise ServiceValidationError(
                f"Ingestion tables are missing ({required}). Run 'alembic upgrade head' before starting ingestion."
            )
        logger.warning("Creating missing ingestion infrastructure tables automatically")
        DataSource.__table__.create(bind=bind, checkfirst=True)
        IngestionRun.__table__.create(bind=bind, checkfirst=True)
        RawIngestionPayload.__table__.create(bind=bind, checkfirst=True)

    def get_required_data_source(self, data_source_id: UUID) -> DataSource:
        """Return a data source by id or raise a service-level not-found error."""

        data_source = self.db.get(DataSource, data_source_id)
        if data_source is None:
            raise NotFoundError(f"Data source with id {data_source_id} not found")
        return data_source

    def get_data_source_by_name(self, source_name: str) -> DataSource | None:
        """Return a data source by source name when present."""

        return (
            self.db.query(DataSource)
            .filter(DataSource.source_name == source_name)
            .one_or_none()
        )

    def list_active_data_sources(self) -> list[DataSource]:
        """Return every active data source in a deterministic order."""

        return (
            self.db.query(DataSource)
            .filter(DataSource.is_active.is_(True))
            .order_by(DataSource.source_name.asc())
            .all()
        )

    def get_or_create_data_source(
        self,
        *,
        source_name: str,
        source_type: DataSourceType,
        base_url: str | None = None,
        is_active: bool = True,
    ) -> DataSource:
        """Return an existing data source or create a new one when missing."""

        data_source = self.get_data_source_by_name(source_name)
        if data_source is None:
            data_source = DataSource(
                source_name=source_name,
                source_type=source_type,
                base_url=base_url,
                is_active=is_active,
            )
            self.db.add(data_source)
            self._commit()
            self.db.refresh(data_source)
            return data_source

        updated = False
        if data_source.source_type != source_type:
            data_source.source_type = source_type
            updated = True
        if data_source.base_url != base_url:
            data_source.base_url = base_url
            updated = True
        if data_source.is_active != is_active:
            data_source.is_active = is_active
            updated = True
        if updated:
            self._commit()
            self.db.refresh(data_source)
        return data_source

    def ensure_registered_data_source(
        self,
        *,
        source_name: str,
        source_type: DataSourceType,
        base_url: str | None = None,
        default_is_active: bool = True,
    ) -> DataSource:
        """Ensure a configured data source exists without re-enabling an existing disabled row."""

        data_source = self.get_data_source_by_name(source_name)
        if data_source is None:
            return self.get_or_create_data_source(
                source_name=source_name,
                source_type=source_type,
                base_url=base_url,
                is_active=default_is_active,
            )

        updated = False
        if data_source.source_type != source_type:
            data_source.source_type = source_type
            updated = True
        if data_source.base_url != base_url:
            data_source.base_url = base_url
            updated = True
        if updated:
            self._commit()
            self.db.refresh(data_source)
        return data_source

    def create_ingestion_run(
        self,
        data_source: DataSource,
        *,
        run_type: IngestionRunType,
        metadata_json: dict[str, object] | None = None,
    ) -> IngestionRun:
        """Persist a new running ingestion run."""

        ingestion_run = IngestionRun(
            data_source_id=data_source.id,
            run_type=run_type,
            status=IngestionRunStatus.RUNNING,
            started_at=utc_now(),
            records_fetched=0,
            records_inserted=0,
            records_skipped=0,
            metadata_json=dict(metadata_json or {}),
        )
        self.db.add(ingestion_run)
        self._commit()
        self.db.refresh(ingestion_run)
        return ingestion_run

    def store_raw_payloads(
        self,
        ingestion_run: IngestionRun,
        payloads: list[RawPayloadEnvelope],
    ) -> None:
        """Persist raw payload envelopes for auditability."""

        raw_payload_rows = [
            RawIngestionPayload(
                ingestion_run_id=ingestion_run.id,
                payload_type=self._coerce_payload_type(payload.payload_type),
                source_identifier=payload.source_identifier,
                raw_json=payload.raw_json,
            )
            for payload in payloads
        ]
        self.db.add_all(raw_payload_rows)
        self._commit()

    def finalize_ingestion_run(
        self,
        ingestion_run: IngestionRun,
        *,
        status: IngestionRunStatus,
        records_fetched: int,
        records_inserted: int,
        records_skipped: int,
        metadata_json: dict[str, object] | None = None,
        error_message: str | None = None,
        finished_at: datetime | None = None,
    ) -> IngestionRun:
        """Update counters and terminal status for an ingestion run."""

        ingestion_run.status = status
        ingestion_run.records_fetched = records_fetched
        ingestion_run.records_inserted = records_inserted
        ingestion_run.records_skipped = records_skipped
        ingestion_run.error_message = error_message
        ingestion_run.finished_at = finished_at or utc_now()
        ingestion_run.metadata_json = {
            **(ingestion_run.metadata_json or {}),
            **dict(metadata_json or {}),
        }
        self._commit()
        self.db.refresh(ingestion_run)
        return ingestion_run

    def _commit(self) -> None:
        try:
            self.db.commit()
        except SQLAlchemyError:
            self.db.rollback()
            raise

    @staticmethod
    def _coerce_payload_type(payload_type: IngestionPayloadType | str) -> IngestionPayloadType:
        if isinstance(payload_type, IngestionPayloadType):
            return payload_type
        return IngestionPayloadType(payload_type)
