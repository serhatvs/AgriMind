"""ORM models for ingestion sources, runs, and raw payload storage."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypeAlias
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import DataSourceType, IngestionPayloadType, IngestionRunStatus, IngestionRunType
from app.models.mixins import CreatedAtMixin, TimestampMixin, utc_now

JSONMapping: TypeAlias = dict[str, Any] | list[Any]


class DataSource(TimestampMixin, Base):
    """Configured external source that can be polled by ingestion pipelines."""

    __tablename__ = "data_sources"
    __table_args__ = (
        UniqueConstraint("source_name", name="uq_data_sources_source_name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_type: Mapped[DataSourceType] = mapped_column(
        Enum(
            DataSourceType,
            name="data_source_type_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    ingestion_runs: Mapped[list["IngestionRun"]] = relationship(
        "IngestionRun",
        back_populates="data_source",
        cascade="all, delete-orphan",
        order_by=lambda: IngestionRun.started_at.desc(),
    )


class IngestionRun(Base):
    """Single execution record for an ingestion source."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint("records_fetched >= 0", name="ck_ingestion_runs_records_fetched_non_negative"),
        CheckConstraint("records_inserted >= 0", name="ck_ingestion_runs_records_inserted_non_negative"),
        CheckConstraint("records_skipped >= 0", name="ck_ingestion_runs_records_skipped_non_negative"),
        CheckConstraint(
            "finished_at IS NULL OR finished_at >= started_at",
            name="ck_ingestion_runs_finished_after_started",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    data_source_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("data_sources.id"),
        nullable=False,
        index=True,
    )
    run_type: Mapped[IngestionRunType] = mapped_column(
        Enum(
            IngestionRunType,
            name="ingestion_run_type_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    status: Mapped[IngestionRunStatus] = mapped_column(
        Enum(
            IngestionRunStatus,
            name="ingestion_run_status_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        default=IngestionRunStatus.PENDING,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_fetched: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_inserted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_skipped: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    data_source: Mapped["DataSource"] = relationship("DataSource", back_populates="ingestion_runs")
    raw_payloads: Mapped[list["RawIngestionPayload"]] = relationship(
        "RawIngestionPayload",
        back_populates="ingestion_run",
        cascade="all, delete-orphan",
        order_by=lambda: RawIngestionPayload.created_at.asc(),
    )


class RawIngestionPayload(CreatedAtMixin, Base):
    """Raw upstream payload persisted before normalization for auditability."""

    __tablename__ = "raw_ingestion_payloads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ingestion_run_id: Mapped[int] = mapped_column(Integer, ForeignKey("ingestion_runs.id"), nullable=False, index=True)
    payload_type: Mapped[IngestionPayloadType] = mapped_column(
        Enum(
            IngestionPayloadType,
            name="ingestion_payload_type_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    source_identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    raw_json: Mapped["JSONMapping"] = mapped_column(JSON, nullable=False)

    ingestion_run: Mapped["IngestionRun"] = relationship("IngestionRun", back_populates="raw_payloads")
