from app.models.crop_price import CropPrice
from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
    WaterSourceType,
)
from app.models.field import Field
from app.models.field_crop_cycle import FieldCropCycle
from app.models.input_cost import InputCost
from app.models.soil_test import SoilTest
from app.models.weather_history import WeatherHistory
from app.services.soil_service import get_latest_soil_test_for_field
from seed import SEED_TAG, build_field_specs, seed


def _seed_field_count(db) -> int:
    return db.query(Field).filter(Field.notes.like(f"{SEED_TAG}%")).count()


def _seed_soil_count(db) -> int:
    return db.query(SoilTest).filter(SoilTest.notes.like(f"{SEED_TAG}%")).count()


def _seed_crop_count(db) -> int:
    return db.query(CropProfile).filter(CropProfile.notes.like(f"{SEED_TAG}%")).count()


def _seed_crop_price_count(db) -> int:
    return db.query(CropPrice).join(CropProfile, CropProfile.id == CropPrice.crop_id).filter(CropProfile.notes.like(f"{SEED_TAG}%")).count()


def _seed_input_cost_count(db) -> int:
    return db.query(InputCost).join(CropProfile, CropProfile.id == InputCost.crop_id).filter(CropProfile.notes.like(f"{SEED_TAG}%")).count()


def _seed_cycle_count(db) -> int:
    return (
        db.query(FieldCropCycle)
        .join(Field, Field.id == FieldCropCycle.field_id)
        .filter(Field.notes.like(f"{SEED_TAG}%"))
        .count()
    )


def _seed_weather_count(db) -> int:
    return (
        db.query(WeatherHistory)
        .join(Field, Field.id == WeatherHistory.field_id)
        .filter(Field.notes.like(f"{SEED_TAG}%"))
        .count()
    )


def test_seed_creates_expected_seed_managed_counts(db):
    seed(db)

    assert _seed_field_count(db) == 50
    assert _seed_soil_count(db) == 50
    assert _seed_crop_count(db) == 5
    assert _seed_crop_price_count(db) == 5
    assert _seed_input_cost_count(db) == 5
    assert _seed_cycle_count(db) == 5
    assert _seed_weather_count(db) == 140

    seeded_crops = db.query(CropProfile).filter(CropProfile.notes.like(f"{SEED_TAG}%")).all()
    crop_names = {crop.crop_name.lower() for crop in seeded_crops}
    assert crop_names == {"blackberry", "corn", "wheat", "sunflower", "chickpea"}
    assert all(crop.optimal_temp_min_c is not None for crop in seeded_crops)
    assert all(crop.optimal_temp_max_c is not None for crop in seeded_crops)
    assert all(crop.rainfall_requirement_mm is not None for crop in seeded_crops)
    assert all(crop.frost_tolerance_days is not None for crop in seeded_crops)
    assert all(crop.heat_tolerance_days is not None for crop in seeded_crops)
    assert all(crop.target_nitrogen_ppm is not None for crop in seeded_crops)
    assert all(crop.target_phosphorus_ppm is not None for crop in seeded_crops)
    assert all(crop.target_potassium_ppm is not None for crop in seeded_crops)
    assert all(crop.growth_stages for crop in seeded_crops)
    assert all(crop.crop_price is not None for crop in seeded_crops)
    assert all(crop.input_cost is not None for crop in seeded_crops)


def test_seed_rerun_does_not_duplicate_seed_records(db):
    seed(db)
    first_counts = (
        _seed_field_count(db),
        _seed_soil_count(db),
        _seed_crop_count(db),
        _seed_cycle_count(db),
        _seed_weather_count(db),
    )

    seed(db)
    second_counts = (
        _seed_field_count(db),
        _seed_soil_count(db),
        _seed_crop_count(db),
        _seed_cycle_count(db),
        _seed_weather_count(db),
    )

    assert first_counts == second_counts == (50, 50, 5, 5, 140)


def test_seed_updates_existing_seed_managed_fields_in_place(db):
    seed(db)
    expected_fields = {spec.slug: spec for spec in build_field_specs()}
    field = db.query(Field).filter(Field.notes.like(f"{SEED_TAG} field_slug=%")).first()
    assert field is not None

    field_id = field.id
    slug = field.notes.split("field_slug=", maxsplit=1)[1].split(" | ", maxsplit=1)[0]
    field.area_hectares = 999.0
    field.irrigation_available = not field.irrigation_available
    db.commit()

    seed(db)

    refreshed = db.query(Field).filter(Field.id == field_id).first()
    assert refreshed is not None
    assert refreshed.area_hectares == expected_fields[slug].area_hectares
    assert refreshed.irrigation_available == expected_fields[slug].irrigation_available


def test_seed_preserves_unrelated_user_created_rows(db):
    user_field = Field(
        name="Custom Trial Field",
        location_name="User Test Zone",
        latitude=35.0,
        longitude=-97.0,
        area_hectares=6.5,
        slope_percent=2.0,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=70,
        drainage_quality="good",
    )
    user_crop = CropProfile(
        crop_name="Custom Millet",
        scientific_name="Pennisetum glaucum",
        ideal_ph_min=6.0,
        ideal_ph_max=7.2,
        tolerable_ph_min=5.5,
        tolerable_ph_max=7.8,
        water_requirement_level=WaterRequirementLevel.LOW,
        drainage_requirement=CropDrainageRequirement.GOOD,
        frost_sensitivity=CropSensitivityLevel.MEDIUM,
        heat_sensitivity=CropSensitivityLevel.LOW,
        salinity_tolerance=CropPreferenceLevel.MODERATE,
        rooting_depth_cm=100.0,
        slope_tolerance=10.0,
        organic_matter_preference=CropPreferenceLevel.MODERATE,
    )
    db.add_all([user_field, user_crop])
    db.commit()

    seed(db)
    seed(db)

    assert db.query(Field).filter(Field.name == "Custom Trial Field").count() == 1
    assert db.query(CropProfile).filter(CropProfile.crop_name == "Custom Millet").count() == 1


def test_seeded_fields_and_soils_cover_multiple_agronomic_bands(db):
    seed(db)

    fields = db.query(Field).filter(Field.notes.like(f"{SEED_TAG}%")).all()
    soils = db.query(SoilTest).filter(SoilTest.notes.like(f"{SEED_TAG}%")).all()

    assert any(field.irrigation_available for field in fields)
    assert any(not field.irrigation_available for field in fields)
    assert len({field.drainage_quality for field in fields}) >= 4
    assert min(field.slope_percent for field in fields) < 1.0
    assert max(field.slope_percent for field in fields) > 10.0

    assert min(soil.ph for soil in soils) < 5.8
    assert max(soil.ph for soil in soils) > 7.5
    assert min(soil.ec for soil in soils if soil.ec is not None) < 0.5
    assert max(soil.ec for soil in soils if soil.ec is not None) > 3.0
    assert len({soil.texture_class for soil in soils}) >= 5
    assert len({soil.drainage_class for soil in soils if soil.drainage_class is not None}) >= 4


def test_each_seeded_field_has_one_seed_managed_latest_soil_test(db):
    seed(db)

    fields = db.query(Field).filter(Field.notes.like(f"{SEED_TAG}%")).all()

    for field in fields:
        assert db.query(SoilTest).filter(SoilTest.field_id == field.id, SoilTest.notes.like(f"{SEED_TAG}%")).count() == 1
        latest = get_latest_soil_test_for_field(db, field.id)
        assert latest is not None
        assert latest.notes.startswith(SEED_TAG)
