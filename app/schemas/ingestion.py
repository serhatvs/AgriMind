"""Pydantic schemas for ingestion configuration and execution records."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataSourceType, IngestionPayloadType, IngestionRunStatus, IngestionRunType


class DataSourceCreate(BaseModel):
    """Schema used to create a data source configuration."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_name: str = Field(..., min_length=1, max_length=255)
    source_type: DataSourceType
    base_url: str | None = Field(default=None, max_length=1024)
    is_active: bool = True


class DataSourceRead(BaseModel):
    """Schema returned for data source records."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_name: str
    source_type: DataSourceType
    base_url: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class IngestionRunRead(BaseModel):
    """Schema returned for ingestion run records."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    data_source_id: int
    run_type: IngestionRunType
    status: IngestionRunStatus
    started_at: datetime
    finished_at: datetime | None
    records_fetched: int
    records_inserted: int
    records_skipped: int
    error_message: str | None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class RawIngestionPayloadRead(BaseModel):
    """Schema returned for persisted raw ingestion payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ingestion_run_id: int
    payload_type: IngestionPayloadType
    source_identifier: str
    raw_json: dict[str, Any] | list[Any]
    created_at: datetime
