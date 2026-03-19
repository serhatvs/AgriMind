import pytest
from pydantic import ValidationError

from app.models.enums import CropDrainageRequirement, WaterRequirementLevel
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
