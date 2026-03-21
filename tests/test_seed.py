from seed import (
    SEED_TAG,
    build_crop_economic_profile_specs,
    build_crop_specs,
    build_field_specs,
    build_seed_dataset,
    build_soil_specs,
)


def test_seed_dataset_matches_demo_requirements():
    dataset = build_seed_dataset()

    assert len(dataset.fields) == 10
    assert len(dataset.soils) == 10
    assert len(dataset.crops) == 5
    assert len(dataset.economic_profiles) == 5
    assert len(dataset.weather) == 280


def test_seed_includes_required_crop_profiles():
    crop_names = {crop.crop_name.lower() for crop in build_crop_specs()}

    assert crop_names == {"blackberry", "corn", "wheat", "sunflower", "chickpea"}


def test_seeded_fields_cover_varied_demo_conditions():
    fields = build_field_specs()

    assert any(field.irrigation_available for field in fields)
    assert any(not field.irrigation_available for field in fields)
    assert min(field.area_hectares for field in fields) < 5.5
    assert max(field.area_hectares for field in fields) > 50.0
    assert min(field.slope_percent for field in fields) < 1.0
    assert max(field.slope_percent for field in fields) > 10.0
    assert len({field.location_name for field in fields}) == 10


def test_seeded_soils_cover_multiple_agronomic_bands():
    soils = build_soil_specs()

    assert min(soil.ph for soil in soils) <= 5.9
    assert max(soil.ph for soil in soils) >= 7.5
    assert min(soil.ec for soil in soils) < 0.4
    assert max(soil.ec for soil in soils) > 2.0
    assert len({soil.texture_class for soil in soils}) >= 5
    assert len({soil.drainage_class for soil in soils}) >= 4


def test_seed_tag_is_stable_for_idempotent_seed_management():
    assert SEED_TAG == "[agrimind-demo-seed:v1]"


def test_seed_includes_required_crop_economic_profiles():
    economic_profile_names = {profile.crop_name.lower() for profile in build_crop_economic_profile_specs()}

    assert economic_profile_names == {"blackberry", "corn", "wheat", "sunflower", "chickpea"}
