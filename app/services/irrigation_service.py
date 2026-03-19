"""Rule-based irrigation planning for weekly field management."""

from __future__ import annotations

from math import ceil
from typing import TYPE_CHECKING, Sequence

from app.models.enums import ManagementNeedLevel, WaterRequirementLevel
from app.schemas.management import IrrigationPlanRead, ManagementBlocker, ManagementPriority

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile
    from app.models.field import Field
    from app.models.soil_test import SoilTest
    from app.models.weather_history import WeatherHistory
    from app.services.lifecycle_service import LifecycleStageResult


class IrrigationService:
    """Build rule-based irrigation guidance for a planning week."""

    _BASELINE_BY_WATER_LEVEL = {
        WaterRequirementLevel.LOW: 20.0,
        WaterRequirementLevel.MEDIUM: 30.0,
        WaterRequirementLevel.HIGH: 40.0,
    }
    _STAGE_MULTIPLIER = {
        ManagementNeedLevel.LOW: 0.8,
        ManagementNeedLevel.MEDIUM: 1.0,
        ManagementNeedLevel.HIGH: 1.2,
    }

    def build_weekly_irrigation(
        self,
        *,
        field_obj: "Field",
        crop: "CropProfile",
        stage: "LifecycleStageResult",
        soil_test: "SoilTest | None",
        recent_weather: Sequence["WeatherHistory"],
    ) -> tuple[IrrigationPlanRead, list[ManagementBlocker]]:
        """Return the irrigation recommendation and any recoverable blockers."""

        gross_need = self._baseline_weekly_need(crop) * self._STAGE_MULTIPLIER[stage.irrigation_need]
        notes: list[str] = []
        blockers: list[ManagementBlocker] = []

        average_weekly_rainfall = self._average_weekly_rainfall(recent_weather)
        if average_weekly_rainfall is None:
            effective_rainfall = 0.0
            notes.append("Recent rainfall history is unavailable; no rainfall adjustment was applied.")
        else:
            effective_rainfall = min(gross_need * 0.6, average_weekly_rainfall * 0.8)
            if effective_rainfall > 0:
                notes.append(f"Recent rainfall offsets {round(effective_rainfall, 2)} mm of weekly irrigation demand.")

        total_mm = round(max(gross_need - effective_rainfall, 0.0), 2)
        if total_mm <= 0:
            frequency_per_week = 0
            mm_per_event = 0.0
            notes.append("No supplemental irrigation is recommended for this week.")
        else:
            frequency_per_week = self._frequency_per_week(soil_test, stage.irrigation_need)
            mm_per_event = round(total_mm / frequency_per_week, 2)

        priority = self._priority_from_need(stage.irrigation_need)
        if not field_obj.irrigation_available and total_mm > 0:
            blockers.append(
                ManagementBlocker(
                    code="irrigation_unavailable",
                    message="Field irrigation is unavailable for the planned weekly water demand.",
                    priority=ManagementPriority.HIGH,
                )
            )
            notes.append("Irrigation is not available on this field; manual intervention is required.")
            priority = ManagementPriority.HIGH

        return (
            IrrigationPlanRead(
                total_mm=total_mm,
                frequency_per_week=frequency_per_week,
                mm_per_event=mm_per_event,
                notes=notes,
                priority=priority,
            ),
            blockers,
        )

    def _baseline_weekly_need(self, crop: "CropProfile") -> float:
        total_cycle_weeks = max(1, ceil(sum(int(stage["duration_days"]) for stage in crop.growth_stages) / 7))
        if crop.rainfall_requirement_mm is not None and crop.rainfall_requirement_mm > 0:
            return round(crop.rainfall_requirement_mm / total_cycle_weeks, 2)
        return self._BASELINE_BY_WATER_LEVEL[crop.water_requirement_level]

    @staticmethod
    def _average_weekly_rainfall(recent_weather: Sequence["WeatherHistory"]) -> float | None:
        if not recent_weather:
            return None

        observation_days = max(len(recent_weather), 1)
        total_rainfall = sum(record.rainfall_mm for record in recent_weather)
        return round((total_rainfall / observation_days) * 7, 2)

    def _frequency_per_week(
        self,
        soil_test: "SoilTest | None",
        stage_need: ManagementNeedLevel,
    ) -> int:
        texture = (soil_test.texture_class.lower() if soil_test and soil_test.texture_class else "")
        water_holding_capacity = soil_test.water_holding_capacity if soil_test is not None else None

        if (water_holding_capacity is not None and water_holding_capacity < 15) or "sand" in texture:
            frequency = 3
        elif (water_holding_capacity is not None and water_holding_capacity > 25) or "clay" in texture:
            frequency = 1
        else:
            frequency = 2

        if stage_need is ManagementNeedLevel.HIGH:
            frequency += 1
        return max(1, min(frequency, 4))

    @staticmethod
    def _priority_from_need(need_level: ManagementNeedLevel) -> ManagementPriority:
        return {
            ManagementNeedLevel.LOW: ManagementPriority.LOW,
            ManagementNeedLevel.MEDIUM: ManagementPriority.MEDIUM,
            ManagementNeedLevel.HIGH: ManagementPriority.HIGH,
        }[need_level]
