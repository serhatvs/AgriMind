"""Read-only schemas for dashboard overview responses."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DashboardTotalsRead(BaseModel):
    """Aggregate totals displayed in the dashboard overview."""

    fields: int
    soil_tests: int
    crop_profiles: int


class DashboardCoverageRead(BaseModel):
    """Basic field-data coverage metrics."""

    fields_with_soil_tests: int
    fields_without_soil_tests: int


class DashboardRecentFieldRead(BaseModel):
    """Recent field summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location_name: str
    updated_at: datetime


class DashboardRecentSoilTestRead(BaseModel):
    """Recent soil-test summary with field context."""

    id: int
    field_id: int
    field_name: str
    sample_date: datetime
    created_at: datetime


class DashboardRecentCropProfileRead(BaseModel):
    """Recent crop-profile summary."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    crop_name: str
    scientific_name: str | None
    updated_at: datetime


class DashboardOverviewRead(BaseModel):
    """Top-level dashboard overview payload."""

    totals: DashboardTotalsRead
    coverage: DashboardCoverageRead
    recent_fields: list[DashboardRecentFieldRead]
    recent_soil_tests: list[DashboardRecentSoilTestRead]
    recent_crop_profiles: list[DashboardRecentCropProfileRead]
