import pytest
from pydantic import ValidationError

from app.models.enums import CropDrainageRequirement, ManagementNeedLevel, WaterRequirementLevel
from app.schemas.crop_profile import CropProfileCreate, CropProfileUpdate


def test_crop_profile_create_requires_core_fields():
    """Test that create validation still requires the crop requirement core."""
    with pytest.raises(ValidationError):
        CropProfileCreate(
            crop_name="Wheat",
            ideal_ph_min=6.0,
            ideal_ph_max=7.0,
            tolerable_ph_min=5.5,
            tolerable_ph_max=7.5,
            water_requirement_level="medium",
            drainage_requirement="good",
            frost_sensitivity="medium",
        )


def test_crop_profile_create_accepts_legacy_aliases():
    """Test that legacy crop field names still map to the canonical contract."""
    crop = CropProfileCreate(
        name="Wheat",
        optimal_ph_min=6.0,
        optimal_ph_max=7.0,
        min_ph=5.5,
        max_ph=7.5,
        water_requirement="medium",
        drainage_requirement="good",
        frost_sensitivity="medium",
        heat_sensitivity="medium",
    )

    assert crop.crop_name == "Wheat"
    assert crop.ideal_ph_min == 6.0
    assert crop.tolerable_ph_max == 7.5
    assert crop.water_requirement_level is WaterRequirementLevel.MEDIUM


def test_crop_profile_create_rejects_invalid_ph_ranges():
    """Test that ideal pH ranges must stay inside tolerable bounds."""
    with pytest.raises(ValidationError):
        CropProfileCreate(
            crop_name="Corn",
            ideal_ph_min=5.0,
            ideal_ph_max=7.0,
            tolerable_ph_min=5.5,
            tolerable_ph_max=7.5,
            water_requirement_level="high",
            drainage_requirement="good",
            frost_sensitivity="high",
            heat_sensitivity="medium",
        )


def test_crop_profile_update_parses_enums_and_ranges():
    """Test that partial updates still parse enum values and numeric ranges."""
    update = CropProfileUpdate(
        water_requirement_level="low",
        drainage_requirement="excellent",
        slope_tolerance=8.0,
    )

    assert update.water_requirement_level is WaterRequirementLevel.LOW
    assert update.drainage_requirement is CropDrainageRequirement.EXCELLENT
    assert update.slope_tolerance == 8.0


def test_crop_profile_update_accepts_climate_fields_and_aliases():
    update = CropProfileUpdate(
        optimal_temp_min_c=16.0,
        optimal_temp_max_c=24.0,
        rainfall_requirement=900.0,
        frost_tolerance=12,
        heat_tolerance=18,
    )

    assert update.optimal_temp_min_c == 16.0
    assert update.optimal_temp_max_c == 24.0
    assert update.rainfall_requirement_mm == 900.0
    assert update.frost_tolerance_days == 12
    assert update.heat_tolerance_days == 18


def test_crop_profile_create_rejects_invalid_optimal_temperature_range():
    with pytest.raises(ValidationError):
        CropProfileCreate(
            crop_name="Blackberry",
            scientific_name="Rubus fruticosus",
            ideal_ph_min=5.5,
            ideal_ph_max=6.5,
            tolerable_ph_min=5.2,
            tolerable_ph_max=6.8,
            water_requirement_level="high",
            drainage_requirement="good",
            frost_sensitivity="medium",
            heat_sensitivity="medium",
            optimal_temp_min_c=25.0,
            optimal_temp_max_c=20.0,
        )


def test_crop_profile_create_accepts_growth_stages():
    crop = CropProfileCreate(
        crop_name="Corn",
        ideal_ph_min=6.0,
        ideal_ph_max=6.8,
        tolerable_ph_min=5.8,
        tolerable_ph_max=7.2,
        water_requirement_level="high",
        drainage_requirement="moderate",
        frost_sensitivity="high",
        heat_sensitivity="medium",
        growth_stages=[
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
        ],
    )

    assert len(crop.growth_stages) == 2
    assert crop.growth_stages[0].name == "germination"
    assert crop.growth_stages[0].irrigation_need is ManagementNeedLevel.MEDIUM


def test_crop_profile_create_accepts_nutrient_target_aliases():
    crop = CropProfileCreate(
        crop_name="Corn",
        ideal_ph_min=6.0,
        ideal_ph_max=6.8,
        tolerable_ph_min=5.8,
        tolerable_ph_max=7.2,
        water_requirement_level="high",
        drainage_requirement="moderate",
        frost_sensitivity="high",
        heat_sensitivity="medium",
        min_nitrogen_ppm=60.0,
        min_phosphorus_ppm=28.0,
        min_potassium_ppm=220.0,
    )

    assert crop.target_nitrogen_ppm == 60.0
    assert crop.target_phosphorus_ppm == 28.0
    assert crop.target_potassium_ppm == 220.0


def test_crop_profile_create_rejects_duplicate_growth_stage_names():
    with pytest.raises(ValidationError):
        CropProfileCreate(
            crop_name="Corn",
            ideal_ph_min=6.0,
            ideal_ph_max=6.8,
            tolerable_ph_min=5.8,
            tolerable_ph_max=7.2,
            water_requirement_level="high",
            drainage_requirement="moderate",
            frost_sensitivity="high",
            heat_sensitivity="medium",
            growth_stages=[
                {
                    "name": "Vegetative",
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
            ],
        )


def test_crop_profile_create_rejects_blank_growth_stage_name():
    with pytest.raises(ValidationError):
        CropProfileCreate(
            crop_name="Corn",
            ideal_ph_min=6.0,
            ideal_ph_max=6.8,
            tolerable_ph_min=5.8,
            tolerable_ph_max=7.2,
            water_requirement_level="high",
            drainage_requirement="moderate",
            frost_sensitivity="high",
            heat_sensitivity="medium",
            growth_stages=[
                {
                    "name": "  ",
                    "duration_days": 7,
                    "irrigation_need": "medium",
                    "fertilizer_need": "low",
                }
            ],
        )


def test_crop_profile_create_rejects_non_positive_growth_stage_duration():
    with pytest.raises(ValidationError):
        CropProfileCreate(
            crop_name="Corn",
            ideal_ph_min=6.0,
            ideal_ph_max=6.8,
            tolerable_ph_min=5.8,
            tolerable_ph_max=7.2,
            water_requirement_level="high",
            drainage_requirement="moderate",
            frost_sensitivity="high",
            heat_sensitivity="medium",
            growth_stages=[
                {
                    "name": "germination",
                    "duration_days": 0,
                    "irrigation_need": "medium",
                    "fertilizer_need": "low",
                }
            ],
        )


def test_crop_profile_create_rejects_invalid_growth_stage_need_level():
    with pytest.raises(ValidationError):
        CropProfileCreate(
            crop_name="Corn",
            ideal_ph_min=6.0,
            ideal_ph_max=6.8,
            tolerable_ph_min=5.8,
            tolerable_ph_max=7.2,
            water_requirement_level="high",
            drainage_requirement="moderate",
            frost_sensitivity="high",
            heat_sensitivity="medium",
            growth_stages=[
                {
                    "name": "germination",
                    "duration_days": 7,
                    "irrigation_need": "critical",
                    "fertilizer_need": "low",
                }
            ],
        )
