from types import SimpleNamespace

from app.models.enums import ManagementNeedLevel, WaterRequirementLevel
from app.schemas.management import ManagementPriority
from app.services.irrigation_service import IrrigationService
from app.services.lifecycle_service import LifecycleStageResult


def _build_crop(**overrides):
    values = {
        "rainfall_requirement_mm": 560.0,
        "growth_stages": [
            {"duration_days": 14},
            {"duration_days": 14},
            {"duration_days": 14},
            {"duration_days": 14},
        ],
        "water_requirement_level": WaterRequirementLevel.HIGH,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _build_field(**overrides):
    values = {"irrigation_available": True}
    values.update(overrides)
    return SimpleNamespace(**values)


def _build_soil(**overrides):
    values = {"water_holding_capacity": 12.0, "texture_class": "sandy loam"}
    values.update(overrides)
    return SimpleNamespace(**values)


def _build_stage(**overrides):
    values = {
        "stage_name": "vegetative",
        "stage_index": 1,
        "day_offset": 7,
        "stage_start_date": None,
        "stage_end_date": None,
        "irrigation_need": ManagementNeedLevel.HIGH,
        "fertilizer_need": ManagementNeedLevel.MEDIUM,
    }
    values.update(overrides)
    return LifecycleStageResult(**values)


def test_irrigation_service_applies_stage_multiplier_and_rainfall_adjustment():
    service = IrrigationService()

    recommendation, blockers = service.build_weekly_irrigation(
        field_obj=_build_field(),
        crop=_build_crop(),
        stage=_build_stage(irrigation_need=ManagementNeedLevel.HIGH),
        soil_test=_build_soil(water_holding_capacity=20.0, texture_class="loam"),
        recent_weather=[SimpleNamespace(rainfall_mm=4.0) for _ in range(7)],
    )

    assert blockers == []
    assert recommendation.total_mm == 61.6
    assert recommendation.frequency_per_week == 3
    assert recommendation.mm_per_event == 20.53
    assert recommendation.priority is ManagementPriority.HIGH


def test_irrigation_service_uses_soil_retention_to_set_frequency():
    service = IrrigationService()

    recommendation, _ = service.build_weekly_irrigation(
        field_obj=_build_field(),
        crop=_build_crop(rainfall_requirement_mm=None, water_requirement_level=WaterRequirementLevel.MEDIUM),
        stage=_build_stage(irrigation_need=ManagementNeedLevel.MEDIUM),
        soil_test=_build_soil(water_holding_capacity=28.0, texture_class="clay loam"),
        recent_weather=[],
    )

    assert recommendation.total_mm == 30.0
    assert recommendation.frequency_per_week == 1
    assert recommendation.mm_per_event == 30.0


def test_irrigation_service_surfaces_unavailable_irrigation_as_blocker():
    service = IrrigationService()

    recommendation, blockers = service.build_weekly_irrigation(
        field_obj=_build_field(irrigation_available=False),
        crop=_build_crop(),
        stage=_build_stage(irrigation_need=ManagementNeedLevel.MEDIUM),
        soil_test=_build_soil(),
        recent_weather=[],
    )

    assert recommendation.priority is ManagementPriority.HIGH
    assert blockers[0].code == "irrigation_unavailable"
