from datetime import date

from app.schemas.management import (
    FertilizerActionRead,
    IrrigationPlanRead,
    ManagementActionRead,
    ManagementBlocker,
    ManagementPlanRead,
    ManagementPlanStatus,
    ManagementPriority,
    NutrientGapRead,
    WeeklyManagementPlanRead,
)


def test_management_plan_schema_serializes_nested_weekly_entries():
    plan = ManagementPlanRead(
        status=ManagementPlanStatus.READY,
        field_id=1,
        crop_id=2,
        sowing_date=date(2026, 3, 1),
        target_date=date(2026, 3, 8),
        current_stage="vegetative",
        blockers=[
            ManagementBlocker(
                code="missing_target_phosphorus_ppm",
                message="Crop nutrient target 'target_phosphorus_ppm' is not configured.",
                priority=ManagementPriority.MEDIUM,
            )
        ],
        weekly_plan=[
            WeeklyManagementPlanRead(
                week_index=0,
                start_date=date(2026, 3, 8),
                end_date=date(2026, 3, 14),
                stage_name="vegetative",
                irrigation=IrrigationPlanRead(
                    total_mm=22.5,
                    frequency_per_week=2,
                    mm_per_event=11.25,
                    notes=["Recent rainfall offsets 4.0 mm of weekly irrigation demand."],
                    priority=ManagementPriority.HIGH,
                ),
                fertilizer_actions=[
                    FertilizerActionRead(
                        planned_date=date(2026, 3, 8),
                        stage_name="vegetative",
                        product="DAP (18-46-0)",
                        priority=ManagementPriority.HIGH,
                        nutrient_gaps=[
                            NutrientGapRead(
                                nutrient="nitrogen",
                                current_ppm=30.0,
                                target_ppm=60.0,
                                deficit_ppm=30.0,
                                severity=ManagementPriority.HIGH,
                            )
                        ],
                        notes=["Immediate corrective application due to a high nutrient deficit."],
                    )
                ],
                notes=["A lifecycle stage transition occurs during this planning week."],
            )
        ],
        action_list=[
            ManagementActionRead(
                action_type="irrigation",
                title="Apply irrigation",
                details="Apply 22.5 mm across 2 events (11.25 mm/event).",
                priority=ManagementPriority.HIGH,
                week_index=0,
                planned_date=date(2026, 3, 8),
            )
        ],
    )

    payload = plan.model_dump(mode="json")

    assert payload["status"] == "ready"
    assert payload["weekly_plan"][0]["irrigation"]["priority"] == "high"
    assert payload["weekly_plan"][0]["fertilizer_actions"][0]["product"] == "DAP (18-46-0)"
    assert payload["action_list"][0]["action_type"] == "irrigation"
