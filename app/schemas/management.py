"""Schemas for field management planning outputs."""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class ManagementPlanStatus(str, Enum):
    """Overall readiness of the generated management plan."""

    READY = "ready"
    PARTIAL = "partial"


class ManagementPriority(str, Enum):
    """Priority used for weekly recommendations and flattened actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ManagementBlocker(BaseModel):
    """Recoverable issue surfaced alongside a partial management plan."""

    code: str
    message: str
    priority: ManagementPriority


class NutrientGapRead(BaseModel):
    """Single nutrient deficit used to justify fertilizer recommendations."""

    nutrient: str
    current_ppm: float
    target_ppm: float
    deficit_ppm: float
    severity: ManagementPriority


class IrrigationPlanRead(BaseModel):
    """Structured irrigation recommendation for a single planning week."""

    total_mm: float
    frequency_per_week: int
    mm_per_event: float
    notes: list[str] = Field(default_factory=list)
    priority: ManagementPriority


class FertilizerActionRead(BaseModel):
    """Structured fertilizer action for a weekly management plan."""

    planned_date: date
    stage_name: str
    product: str
    priority: ManagementPriority
    nutrient_gaps: list[NutrientGapRead] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class WeeklyManagementPlanRead(BaseModel):
    """Weekly field management plan entry."""

    week_index: int
    start_date: date
    end_date: date
    stage_name: str
    irrigation: IrrigationPlanRead
    fertilizer_actions: list[FertilizerActionRead] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ManagementActionRead(BaseModel):
    """Flattened action item derived from weekly management entries."""

    action_type: str
    title: str
    details: str
    priority: ManagementPriority
    week_index: int
    planned_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    stage_name: str | None = None
    product: str | None = None
    total_mm: float | None = None
    frequency_per_week: int | None = None


class ManagementPlanRead(BaseModel):
    """Response payload returned by the management-planning API."""

    model_config = ConfigDict(from_attributes=True)

    status: ManagementPlanStatus
    field_id: int
    crop_id: int
    sowing_date: date
    target_date: date
    current_stage: str
    blockers: list[ManagementBlocker] = Field(default_factory=list)
    weekly_plan: list[WeeklyManagementPlanRead] = Field(default_factory=list)
    action_list: list[ManagementActionRead] = Field(default_factory=list)
