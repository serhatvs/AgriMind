from datetime import date, datetime

import pytest

from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropSensitivityLevel,
    ManagementNeedLevel,
    WaterRequirementLevel,
    WaterSourceType,
)
from app.models.field import Field
from app.models.field_crop_cycle import FieldCropCycle
from app.services.lifecycle_service import LifecycleService


def _build_field() -> Field:
    return Field(
        name="Lifecycle Field",
        location_name="Lifecycle Valley",
        latitude=39.1012,
        longitude=-94.5788,
        area_hectares=8.0,
        elevation_meters=215.0,
        slope_percent=1.5,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=82,
        drainage_quality="good",
    )


def _build_crop(*, growth_stages: list[dict[str, object]] | None = None) -> CropProfile:
    stage_definitions = growth_stages if growth_stages is not None else [
        {
            "name": "germination",
            "duration_days": 7,
            "irrigation_need": "medium",
            "fertilizer_need": "low",
        },
        {
            "name": "vegetative",
            "duration_days": 21,
            "irrigation_need": "high",
            "fertilizer_need": "medium",
        },
        {
            "name": "reproductive",
            "duration_days": 14,
            "irrigation_need": "medium",
            "fertilizer_need": "high",
        },
    ]

    return CropProfile(
        crop_name="Corn",
        scientific_name="Zea mays",
        ideal_ph_min=6.0,
        ideal_ph_max=6.8,
        tolerable_ph_min=5.8,
        tolerable_ph_max=7.2,
        water_requirement_level=WaterRequirementLevel.HIGH,
        drainage_requirement=CropDrainageRequirement.MODERATE,
        frost_sensitivity=CropSensitivityLevel.HIGH,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        growth_stages=stage_definitions,
    )


def test_calculate_current_stage_returns_first_stage_and_updates_cycle(db):
    field = _build_field()
    crop = _build_crop()
    cycle = FieldCropCycle(
        field=field,
        crop=crop,
        sowing_date=date(2026, 3, 1),
        current_stage="planned",
    )
    db.add_all([field, crop, cycle])
    db.commit()

    result = LifecycleService(db).calculate_current_stage(field, crop, date(2026, 3, 1))
    db.expire_all()
    persisted_cycle = db.query(FieldCropCycle).filter(FieldCropCycle.id == cycle.id).one()

    assert result.stage_name == "germination"
    assert result.stage_index == 0
    assert result.day_offset == 0
    assert result.stage_start_date == date(2026, 3, 1)
    assert result.stage_end_date == date(2026, 3, 7)
    assert persisted_cycle.current_stage == "germination"


def test_calculate_current_stage_moves_to_next_stage_on_boundary_day(db):
    field = _build_field()
    crop = _build_crop()
    cycle = FieldCropCycle(
        field=field,
        crop=crop,
        sowing_date=date(2026, 3, 1),
        current_stage="germination",
    )
    db.add_all([field, crop, cycle])
    db.commit()

    result = LifecycleService(db).calculate_current_stage(field, crop, date(2026, 3, 8))

    assert result.stage_name == "vegetative"
    assert result.stage_index == 1
    assert result.stage_start_date == date(2026, 3, 8)
    assert result.stage_end_date == date(2026, 3, 28)


def test_calculate_current_stage_clamps_to_final_stage_after_total_duration(db):
    field = _build_field()
    crop = _build_crop()
    cycle = FieldCropCycle(
        field=field,
        crop=crop,
        sowing_date=date(2026, 3, 1),
        current_stage="vegetative",
    )
    db.add_all([field, crop, cycle])
    db.commit()

    result = LifecycleService(db).calculate_current_stage(field, crop, datetime(2026, 5, 1, 9, 30))

    assert result.stage_name == "reproductive"
    assert result.stage_index == 2
    assert result.irrigation_need is ManagementNeedLevel.MEDIUM
    assert result.fertilizer_need is ManagementNeedLevel.HIGH


def test_lifecycle_service_exposes_stage_based_need_hooks(db):
    field = _build_field()
    crop = _build_crop()
    cycle = FieldCropCycle(
        field=field,
        crop=crop,
        sowing_date=date(2026, 3, 1),
        current_stage="germination",
    )
    db.add_all([field, crop, cycle])
    db.commit()

    service = LifecycleService(db)

    assert service.get_irrigation_need(field, crop, date(2026, 3, 10)) is ManagementNeedLevel.HIGH
    assert service.get_fertilizer_need(field, crop, date(2026, 3, 10)) is ManagementNeedLevel.MEDIUM


def test_lifecycle_service_requires_active_cycle(db):
    field = _build_field()
    crop = _build_crop()
    db.add_all([field, crop])
    db.commit()

    with pytest.raises(ValueError, match="No active crop cycle found"):
        LifecycleService(db).calculate_current_stage(field, crop, date(2026, 3, 1))


def test_lifecycle_service_rejects_crop_cycle_mismatch(db):
    field = _build_field()
    wheat = _build_crop()
    corn = CropProfile(
        crop_name="Wheat",
        scientific_name="Triticum aestivum",
        ideal_ph_min=6.0,
        ideal_ph_max=7.0,
        tolerable_ph_min=5.5,
        tolerable_ph_max=7.5,
        water_requirement_level=WaterRequirementLevel.MEDIUM,
        drainage_requirement=CropDrainageRequirement.GOOD,
        frost_sensitivity=CropSensitivityLevel.MEDIUM,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        growth_stages=[
            {
                "name": "germination",
                "duration_days": 7,
                "irrigation_need": "medium",
                "fertilizer_need": "low",
            }
        ],
    )
    cycle = FieldCropCycle(
        field=field,
        crop=wheat,
        sowing_date=date(2026, 3, 1),
        current_stage="germination",
    )
    db.add_all([field, wheat, corn, cycle])
    db.commit()

    with pytest.raises(ValueError, match="is assigned to crop"):
        LifecycleService(db).calculate_current_stage(field, corn, date(2026, 3, 1))


def test_lifecycle_service_rejects_missing_growth_stages(db):
    field = _build_field()
    crop = _build_crop(growth_stages=[])
    cycle = FieldCropCycle(
        field=field,
        crop=crop,
        sowing_date=date(2026, 3, 1),
        current_stage="planned",
    )
    db.add_all([field, crop, cycle])
    db.commit()

    with pytest.raises(ValueError, match="has no growth stages configured"):
        LifecycleService(db).calculate_current_stage(field, crop, date(2026, 3, 1))


def test_lifecycle_service_rejects_dates_before_sowing(db):
    field = _build_field()
    crop = _build_crop()
    cycle = FieldCropCycle(
        field=field,
        crop=crop,
        sowing_date=date(2026, 3, 1),
        current_stage="planned",
    )
    db.add_all([field, crop, cycle])
    db.commit()

    with pytest.raises(ValueError, match="before sowing_date"):
        LifecycleService(db).calculate_current_stage(field, crop, date(2026, 2, 28))
