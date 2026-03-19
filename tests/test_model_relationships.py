from datetime import datetime, timezone

from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
    WaterSourceType,
)
from app.models.field import Field
from app.models.soil_test import SoilTest


def test_field_soil_test_relationship_and_crop_profile_persist_together(db):
    """Field, soil, and crop records should coexist cleanly in one ranking session."""

    field = Field(
        name="Model Parcel",
        location_name="Model Valley",
        latitude=39.1012,
        longitude=-94.5788,
        area_hectares=12.5,
        elevation_meters=210.0,
        slope_percent=2.5,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=78,
        drainage_quality="good",
    )
    crop = CropProfile(
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
        salinity_tolerance=CropPreferenceLevel.MODERATE,
        rooting_depth_cm=150.0,
        slope_tolerance=6.0,
        organic_matter_preference=CropPreferenceLevel.MODERATE,
    )
    db.add_all([field, crop])
    db.flush()

    soil_test = SoilTest(
        field_id=field.id,
        sample_date=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        ph=6.4,
        ec=0.9,
        organic_matter_percent=3.8,
        nitrogen_ppm=42.0,
        phosphorus_ppm=28.0,
        potassium_ppm=210.0,
        calcium_ppm=1650.0,
        magnesium_ppm=215.0,
        texture_class="loamy",
        drainage_class="good",
        depth_cm=120.0,
        water_holding_capacity=22.0,
    )
    db.add(soil_test)
    db.commit()
    db.expire_all()

    persisted_field = db.query(Field).filter(Field.id == field.id).first()
    persisted_soil = db.query(SoilTest).filter(SoilTest.id == soil_test.id).first()
    persisted_crop = db.query(CropProfile).filter(CropProfile.id == crop.id).first()

    assert persisted_field is not None
    assert persisted_soil is not None
    assert persisted_crop is not None
    assert len(persisted_field.soil_tests) == 1
    assert persisted_field.soil_tests[0].id == persisted_soil.id
    assert persisted_soil.field is not None
    assert persisted_soil.field.id == persisted_field.id
    assert persisted_crop.crop_name == "Corn"
