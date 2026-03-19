from datetime import date, timedelta

from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    ManagementNeedLevel,
    WaterRequirementLevel,
    WaterSourceType,
)
from app.models.field import Field
from app.models.field_crop_cycle import FieldCropCycle
from app.models.soil_test import SoilTest
from app.models.weather_history import WeatherHistory
from app.services.management_service import ManagementService


def _create_field(db, **overrides) -> Field:
    values = {
        "name": "Management Field",
        "location_name": "Planning Valley",
        "latitude": 39.2,
        "longitude": -94.6,
        "area_hectares": 12.0,
        "elevation_meters": 220.0,
        "slope_percent": 2.0,
        "irrigation_available": True,
        "water_source_type": WaterSourceType.WELL,
        "infrastructure_score": 78,
        "drainage_quality": "good",
    }
    values.update(overrides)
    field = Field(**values)
    db.add(field)
    db.flush()
    return field


def _create_crop(db, **overrides) -> CropProfile:
    values = {
        "crop_name": "Corn",
        "scientific_name": "Zea mays",
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 6.8,
        "tolerable_ph_min": 5.8,
        "tolerable_ph_max": 7.2,
        "water_requirement_level": WaterRequirementLevel.HIGH,
        "drainage_requirement": CropDrainageRequirement.MODERATE,
        "frost_sensitivity": CropSensitivityLevel.HIGH,
        "heat_sensitivity": CropSensitivityLevel.MEDIUM,
        "salinity_tolerance": CropPreferenceLevel.MODERATE,
        "rooting_depth_cm": 150.0,
        "slope_tolerance": 8.0,
        "rainfall_requirement_mm": 640.0,
        "organic_matter_preference": CropPreferenceLevel.MODERATE,
        "target_nitrogen_ppm": 60.0,
        "target_phosphorus_ppm": 28.0,
        "target_potassium_ppm": 220.0,
        "growth_stages": [
            {
                "name": "germination",
                "duration_days": 7,
                "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                "fertilizer_need": ManagementNeedLevel.LOW.value,
            },
            {
                "name": "vegetative",
                "duration_days": 21,
                "irrigation_need": ManagementNeedLevel.HIGH.value,
                "fertilizer_need": ManagementNeedLevel.HIGH.value,
            },
            {
                "name": "reproductive",
                "duration_days": 14,
                "irrigation_need": ManagementNeedLevel.MEDIUM.value,
                "fertilizer_need": ManagementNeedLevel.MEDIUM.value,
            },
        ],
    }
    values.update(overrides)
    crop = CropProfile(**values)
    db.add(crop)
    db.flush()
    return crop


def _create_soil_test(db, field_id: int, **overrides) -> SoilTest:
    values = {
        "field_id": field_id,
        "ph": 6.4,
        "ec": 1.1,
        "organic_matter_percent": 3.4,
        "nitrogen_ppm": 30.0,
        "phosphorus_ppm": 18.0,
        "potassium_ppm": 180.0,
        "calcium_ppm": 1700.0,
        "magnesium_ppm": 220.0,
        "texture_class": "loam",
        "drainage_class": "good",
        "depth_cm": 120.0,
        "water_holding_capacity": 19.0,
    }
    values.update(overrides)
    soil_test = SoilTest(**values)
    db.add(soil_test)
    return soil_test


def _create_weather_window(db, field_id: int, window_end: date, days: int = 28) -> None:
    for offset in range(days):
        weather_date = window_end - timedelta(days=(days - 1 - offset))
        db.add(
            WeatherHistory(
                field_id=field_id,
                date=weather_date,
                min_temp=11.0,
                max_temp=24.0,
                avg_temp=17.0,
                rainfall_mm=2.0 if offset % 5 == 0 else 0.5,
                humidity=62.0,
                wind_speed=8.0,
                solar_radiation=16.0,
                et0=3.2,
            )
        )


def test_management_service_builds_eight_week_plan_with_lifecycle_progression(db):
    field = _create_field(db)
    crop = _create_crop(db)
    _create_soil_test(db, field.id)
    _create_weather_window(db, field.id, window_end=date(2026, 3, 8))
    db.add(
        FieldCropCycle(
            field_id=field.id,
            crop_id=crop.id,
            sowing_date=date(2026, 3, 1),
            current_stage="planned",
        )
    )
    db.commit()

    plan = ManagementService(db).get_management_plan(
        field.id,
        target_date=date(2026, 3, 8),
        weeks=8,
    )

    assert plan.status.value == "ready"
    assert len(plan.weekly_plan) == 8
    assert plan.current_stage == "vegetative"
    assert plan.weekly_plan[0].stage_name == "vegetative"
    assert any(week.stage_name == "reproductive" for week in plan.weekly_plan)
    assert any(action.action_type == "irrigation" for action in plan.action_list)
    assert any(action.action_type == "fertilizer" for action in plan.action_list)
    assert all(0 <= action.week_index < 8 for action in plan.action_list)


def test_management_plan_endpoint_returns_partial_when_targets_are_missing(client, db):
    field = _create_field(db)
    crop = _create_crop(db, target_phosphorus_ppm=None)
    _create_soil_test(db, field.id)
    _create_weather_window(db, field.id, window_end=date(2026, 3, 8))
    db.add(
        FieldCropCycle(
            field_id=field.id,
            crop_id=crop.id,
            sowing_date=date(2026, 3, 1),
            current_stage="planned",
        )
    )
    db.commit()

    response = client.get(f"/api/v1/fields/{field.id}/management-plan?target_date=2026-03-08&weeks=8")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "partial"
    assert payload["blockers"][0]["code"] == "missing_target_phosphorus_ppm"


def test_management_plan_endpoint_returns_409_when_active_cycle_is_missing(client, db):
    field = _create_field(db)
    _create_crop(db)
    db.commit()

    response = client.get(f"/api/v1/fields/{field.id}/management-plan?target_date=2026-03-08&weeks=8")

    assert response.status_code == 409
    assert "No active crop cycle found" in response.json()["detail"]
