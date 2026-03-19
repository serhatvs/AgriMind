"""Management-plan orchestration for post-placement field operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app.schemas.management import (
    ManagementActionRead,
    ManagementBlocker,
    ManagementPlanRead,
    ManagementPlanStatus,
    ManagementPriority,
    WeeklyManagementPlanRead,
)
from app.services.crop_service import get_crop
from app.services.fertilizer_service import FertilityAssessment, FertilizerService
from app.services.field_service import get_field
from app.services.irrigation_service import IrrigationService
from app.services.lifecycle_service import LifecycleService, LifecycleStageResult
from app.services.soil_service import get_latest_soil_test_for_field
from app.services.weather_service import WeatherService

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile
    from app.models.field import Field
    from app.models.field_crop_cycle import FieldCropCycle


MAX_PLAN_WEEKS = 12


class ManagementPlanNotFoundError(ValueError):
    """Raised when the requested field does not exist."""


class ManagementPlanConflictError(ValueError):
    """Raised when placement or lifecycle state is missing for planning."""


@dataclass(slots=True)
class ManagementPlanContext:
    """Preloaded state required to build a management plan."""

    field_obj: "Field"
    cycle: "FieldCropCycle"
    crop: "CropProfile"
    current_stage: LifecycleStageResult
    stage_schedule: list[LifecycleStageResult]
    recent_weather: list[object]
    fertilizer_assessment: FertilityAssessment


class ManagementService:
    """Build a structured field management plan from placement state."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.lifecycle_service = LifecycleService(db)
        self.weather_service = WeatherService(db)
        self.irrigation_service = IrrigationService()
        self.fertilizer_service = FertilizerService()

    def get_management_plan(
        self,
        field_id: int,
        *,
        target_date: date,
        weeks: int = 8,
    ) -> ManagementPlanRead:
        """Return a structured management plan for the active crop cycle."""

        if weeks <= 0 or weeks > MAX_PLAN_WEEKS:
            raise ValueError(f"weeks must be between 1 and {MAX_PLAN_WEEKS}.")

        context = self._build_context(field_id=field_id, target_date=target_date)
        blockers = self._dedupe_blockers(context.fertilizer_assessment.blockers)
        weekly_plan: list[WeeklyManagementPlanRead] = []
        action_list: list[ManagementActionRead] = []

        soil_test = get_latest_soil_test_for_field(self.db, field_id)
        for week_index in range(weeks):
            week_start = target_date + timedelta(days=week_index * 7)
            week_end = week_start + timedelta(days=6)
            stage_at_week_start = self._stage_for_date(context.stage_schedule, week_start)
            stage_starts_in_week = [
                stage
                for stage in context.stage_schedule
                if week_start <= stage.stage_start_date <= week_end
            ]
            irrigation, irrigation_blockers = self.irrigation_service.build_weekly_irrigation(
                field_obj=context.field_obj,
                crop=context.crop,
                stage=stage_at_week_start,
                soil_test=soil_test,
                recent_weather=context.recent_weather,
            )
            fertilizer_actions = self.fertilizer_service.build_weekly_actions(
                assessment=context.fertilizer_assessment,
                week_start=week_start,
                stage_at_week_start=stage_at_week_start,
                stage_starts_in_week=stage_starts_in_week,
                include_immediate_correction=week_index == 0,
            )

            blockers = self._dedupe_blockers(blockers + irrigation_blockers)
            weekly_notes: list[str] = []
            if any(stage.stage_start_date > week_start for stage in stage_starts_in_week):
                weekly_notes.append("A lifecycle stage transition occurs during this planning week.")
            if len(stage_starts_in_week) > 1:
                weekly_notes.append("Multiple lifecycle stage starts fall within this week.")

            weekly_plan.append(
                WeeklyManagementPlanRead(
                    week_index=week_index,
                    start_date=week_start,
                    end_date=week_end,
                    stage_name=stage_at_week_start.stage_name,
                    irrigation=irrigation,
                    fertilizer_actions=fertilizer_actions,
                    notes=weekly_notes,
                )
            )
            action_list.extend(
                self._build_week_actions(
                    week_index=week_index,
                    week_start=week_start,
                    week_end=week_end,
                    stage_name=stage_at_week_start.stage_name,
                    irrigation=irrigation,
                    irrigation_blockers=irrigation_blockers,
                    fertilizer_actions=fertilizer_actions,
                )
            )

        if context.fertilizer_assessment.blockers:
            action_list.extend(
                self._build_blocker_actions(
                    week_index=0,
                    week_start=target_date,
                    week_end=target_date + timedelta(days=6),
                    stage_name=context.current_stage.stage_name,
                    blockers=context.fertilizer_assessment.blockers,
                )
            )

        action_list = sorted(
            action_list,
            key=lambda action: (action.week_index, -self._priority_rank(action.priority), action.title),
        )
        status = ManagementPlanStatus.PARTIAL if blockers else ManagementPlanStatus.READY
        return ManagementPlanRead(
            status=status,
            field_id=context.field_obj.id,
            crop_id=context.crop.id,
            sowing_date=context.cycle.sowing_date,
            target_date=target_date,
            current_stage=context.current_stage.stage_name,
            blockers=blockers,
            weekly_plan=weekly_plan,
            action_list=action_list,
        )

    def _build_context(
        self,
        *,
        field_id: int,
        target_date: date,
    ) -> ManagementPlanContext:
        field_obj = get_field(self.db, field_id)
        if field_obj is None:
            raise ManagementPlanNotFoundError("Field not found.")

        cycle = self.lifecycle_service.get_active_cycle(field_id)
        if cycle is None:
            raise ManagementPlanConflictError(f"No active crop cycle found for field {field_id}.")

        crop = cycle.crop or get_crop(self.db, cycle.crop_id)
        if crop is None:
            raise ManagementPlanConflictError(f"Crop {cycle.crop_id} was not found for the active field cycle.")

        if not crop.growth_stages:
            raise ManagementPlanConflictError(f"Crop {crop.id} has no growth stages configured.")

        try:
            current_stage = self.lifecycle_service.calculate_current_stage(field_obj, crop, target_date)
            stage_schedule = self.lifecycle_service.build_stage_schedule(cycle.sowing_date, crop)
        except ValueError as exc:
            raise ManagementPlanConflictError(str(exc)) from exc

        soil_test = get_latest_soil_test_for_field(self.db, field_id)
        recent_weather = self.weather_service.get_weather_window(
            field_id,
            start_date=target_date - timedelta(days=27),
            end_date=target_date,
        )
        fertilizer_assessment = self.fertilizer_service.assess_nutrients(crop=crop, soil_test=soil_test)

        return ManagementPlanContext(
            field_obj=field_obj,
            cycle=cycle,
            crop=crop,
            current_stage=current_stage,
            stage_schedule=stage_schedule,
            recent_weather=recent_weather,
            fertilizer_assessment=fertilizer_assessment,
        )

    def _build_week_actions(
        self,
        *,
        week_index: int,
        week_start: date,
        week_end: date,
        stage_name: str,
        irrigation,
        irrigation_blockers: list[ManagementBlocker],
        fertilizer_actions,
    ) -> list[ManagementActionRead]:
        actions: list[ManagementActionRead] = []
        if irrigation.total_mm > 0:
            actions.append(
                ManagementActionRead(
                    action_type="irrigation",
                    title="Apply irrigation",
                    details=(
                        f"Apply {irrigation.total_mm} mm across {irrigation.frequency_per_week} events "
                        f"({irrigation.mm_per_event} mm/event)."
                    ),
                    priority=irrigation.priority,
                    week_index=week_index,
                    planned_date=week_start,
                    start_date=week_start,
                    end_date=week_end,
                    stage_name=stage_name,
                    total_mm=irrigation.total_mm,
                    frequency_per_week=irrigation.frequency_per_week,
                )
            )

        actions.extend(
            self._build_blocker_actions(
                week_index=week_index,
                week_start=week_start,
                week_end=week_end,
                stage_name=stage_name,
                blockers=irrigation_blockers,
            )
        )

        for action in fertilizer_actions:
            nutrient_summary = ", ".join(gap.nutrient for gap in action.nutrient_gaps)
            actions.append(
                ManagementActionRead(
                    action_type="fertilizer",
                    title=f"Apply {action.product}",
                    details=f"Address nutrient deficits in {nutrient_summary}.",
                    priority=action.priority,
                    week_index=week_index,
                    planned_date=action.planned_date,
                    start_date=week_start,
                    end_date=week_end,
                    stage_name=action.stage_name,
                    product=action.product,
                )
            )
        return actions

    def _build_blocker_actions(
        self,
        *,
        week_index: int,
        week_start: date,
        week_end: date,
        stage_name: str,
        blockers: list[ManagementBlocker],
    ) -> list[ManagementActionRead]:
        actions: list[ManagementActionRead] = []
        for blocker in self._dedupe_blockers(blockers):
            actions.append(
                ManagementActionRead(
                    action_type="blocker",
                    title=blocker.code.replace("_", " ").capitalize(),
                    details=blocker.message,
                    priority=blocker.priority,
                    week_index=week_index,
                    planned_date=week_start,
                    start_date=week_start,
                    end_date=week_end,
                    stage_name=stage_name,
                )
            )
        return actions

    @staticmethod
    def _stage_for_date(
        stage_schedule: list[LifecycleStageResult],
        target_date: date,
    ) -> LifecycleStageResult:
        for stage in stage_schedule:
            if stage.stage_start_date <= target_date <= stage.stage_end_date:
                return stage
        return stage_schedule[-1]

    @staticmethod
    def _dedupe_blockers(blockers: list[ManagementBlocker]) -> list[ManagementBlocker]:
        deduped: list[ManagementBlocker] = []
        seen: set[tuple[str, str]] = set()
        for blocker in blockers:
            key = (blocker.code, blocker.message)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(blocker)
        return deduped

    @staticmethod
    def _priority_rank(priority: ManagementPriority) -> int:
        return {
            ManagementPriority.LOW: 1,
            ManagementPriority.MEDIUM: 2,
            ManagementPriority.HIGH: 3,
        }[priority]
