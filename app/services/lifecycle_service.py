"""Crop lifecycle helpers for time-aware stage resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.models.enums import ManagementNeedLevel
from app.models.field_crop_cycle import FieldCropCycle

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile
    from app.models.field import Field


@dataclass(slots=True)
class LifecycleStageResult:
    """Resolved lifecycle stage and stage-scoped management needs."""

    stage_name: str
    stage_index: int
    day_offset: int
    stage_start_date: date
    stage_end_date: date
    irrigation_need: ManagementNeedLevel
    fertilizer_need: ManagementNeedLevel


class LifecycleService:
    """Resolve crop growth stage and stage-scoped management guidance."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def calculate_current_stage(
        self,
        field_obj: "Field",
        crop: "CropProfile",
        target_date: date | datetime,
    ) -> LifecycleStageResult:
        """Resolve the current stage for the field's active crop cycle."""

        return self._calculate_stage(field_obj, crop, target_date, persist_current_stage=True)

    def preview_stage(
        self,
        field_obj: "Field",
        crop: "CropProfile",
        target_date: date | datetime,
    ) -> LifecycleStageResult:
        """Resolve the current stage without persisting cycle state changes."""

        return self._calculate_stage(field_obj, crop, target_date, persist_current_stage=False)

    def build_stage_schedule(
        self,
        sowing_date: date,
        crop: "CropProfile",
    ) -> list[LifecycleStageResult]:
        """Return the full ordered stage schedule for the crop cycle."""

        if not crop.growth_stages:
            raise ValueError(f"Crop {crop.id} has no growth stages configured.")

        schedule: list[LifecycleStageResult] = []
        stage_start_offset = 0
        for stage_index, raw_stage in enumerate(crop.growth_stages):
            stage_name = self._read_stage_name(raw_stage)
            duration_days = self._read_stage_duration(raw_stage)
            stage_end_offset = stage_start_offset + duration_days - 1
            schedule.append(
                LifecycleStageResult(
                    stage_name=stage_name,
                    stage_index=stage_index,
                    day_offset=stage_start_offset,
                    stage_start_date=sowing_date + timedelta(days=stage_start_offset),
                    stage_end_date=sowing_date + timedelta(days=stage_end_offset),
                    irrigation_need=ManagementNeedLevel(raw_stage["irrigation_need"]),
                    fertilizer_need=ManagementNeedLevel(raw_stage["fertilizer_need"]),
                )
            )
            stage_start_offset = stage_end_offset + 1
        return schedule

    def get_active_cycle(self, field_id: int) -> FieldCropCycle | None:
        """Return the active crop cycle for a field if one exists."""

        return self._get_active_cycle(field_id)

    def _calculate_stage(
        self,
        field_obj: "Field",
        crop: "CropProfile",
        target_date: date | datetime,
        *,
        persist_current_stage: bool,
    ) -> LifecycleStageResult:
        """Resolve the current stage, optionally persisting the cycle stage."""

        cycle = self._get_active_cycle(field_obj.id)
        if cycle is None:
            raise ValueError(f"No active crop cycle found for field {field_obj.id}.")
        if cycle.crop_id != crop.id:
            raise ValueError(
                f"Active crop cycle for field {field_obj.id} is assigned to crop {cycle.crop_id}, not crop {crop.id}."
            )
        if not crop.growth_stages:
            raise ValueError(f"Crop {crop.id} has no growth stages configured.")

        resolved_date = self._coerce_date(target_date)
        if resolved_date < cycle.sowing_date:
            raise ValueError("target_date cannot be before sowing_date.")

        days_since_sowing = (resolved_date - cycle.sowing_date).days
        result = self._resolve_stage(cycle.sowing_date, crop.growth_stages, days_since_sowing)

        if persist_current_stage and cycle.current_stage != result.stage_name:
            cycle.current_stage = result.stage_name
            self.db.flush()

        return result

    def get_irrigation_need(
        self,
        field_obj: "Field",
        crop: "CropProfile",
        target_date: date | datetime,
    ) -> ManagementNeedLevel:
        """Return the irrigation need for the resolved stage."""

        return self.calculate_current_stage(field_obj, crop, target_date).irrigation_need

    def get_fertilizer_need(
        self,
        field_obj: "Field",
        crop: "CropProfile",
        target_date: date | datetime,
    ) -> ManagementNeedLevel:
        """Return the fertilizer need for the resolved stage."""

        return self.calculate_current_stage(field_obj, crop, target_date).fertilizer_need

    def _get_active_cycle(self, field_id: int) -> FieldCropCycle | None:
        return self.db.query(FieldCropCycle).filter(FieldCropCycle.field_id == field_id).first()

    def _resolve_stage(
        self,
        sowing_date: date,
        growth_stages: list[dict[str, Any]],
        day_offset: int,
    ) -> LifecycleStageResult:
        stage_start_offset = 0

        for stage_index, raw_stage in enumerate(growth_stages):
            stage_name = self._read_stage_name(raw_stage)
            duration_days = self._read_stage_duration(raw_stage)
            stage_end_offset = stage_start_offset + duration_days - 1

            if day_offset <= stage_end_offset or stage_index == len(growth_stages) - 1:
                return LifecycleStageResult(
                    stage_name=stage_name,
                    stage_index=stage_index,
                    day_offset=day_offset,
                    stage_start_date=sowing_date + timedelta(days=stage_start_offset),
                    stage_end_date=sowing_date + timedelta(days=stage_end_offset),
                    irrigation_need=ManagementNeedLevel(raw_stage["irrigation_need"]),
                    fertilizer_need=ManagementNeedLevel(raw_stage["fertilizer_need"]),
                )

            stage_start_offset = stage_end_offset + 1

        raise ValueError("Crop growth stage data is invalid.")

    @staticmethod
    def _coerce_date(value: date | datetime) -> date:
        if isinstance(value, datetime):
            return value.date()
        return value

    @staticmethod
    def _read_stage_name(raw_stage: dict[str, Any]) -> str:
        try:
            stage_name = str(raw_stage["name"]).strip()
        except KeyError as exc:
            raise ValueError("Crop growth stage data is invalid.") from exc
        if not stage_name:
            raise ValueError("Crop growth stage data is invalid.")
        return stage_name

    @staticmethod
    def _read_stage_duration(raw_stage: dict[str, Any]) -> int:
        try:
            duration_days = int(raw_stage["duration_days"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Crop growth stage data is invalid.") from exc
        if duration_days <= 0:
            raise ValueError("Crop growth stage data is invalid.")
        return duration_days
