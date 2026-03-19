import pytest

from app.schemas.crop_profile import CropProfileCreate, CropProfileUpdate
from app.schemas.field import FieldCreate
from app.schemas.soil_test import SoilTestCreate, SoilTestUpdate
from app.services.crop_service import create_crop, update_crop
from app.services.dashboard_service import get_dashboard_overview
from app.services.errors import ConflictError, NotFoundError
from app.services.field_service import create_field
from app.services.soil_service import create_soil_test, update_soil_test


def _build_field_schema(name: str) -> FieldCreate:
    return FieldCreate(
        name=name,
        location_name=f"{name} Valley",
        latitude=39.0,
        longitude=-94.0,
        area_hectares=10.0,
        elevation_meters=210.0,
        slope_percent=2.5,
        irrigation_available=True,
        water_source_type="well",
        infrastructure_score=74,
        drainage_quality="good",
    )


def _build_crop_schema(name: str) -> CropProfileCreate:
    return CropProfileCreate(
        crop_name=name,
        scientific_name=f"{name} scientific",
        ideal_ph_min=6.0,
        ideal_ph_max=7.0,
        tolerable_ph_min=5.5,
        tolerable_ph_max=7.5,
        water_requirement_level="medium",
        drainage_requirement="good",
        frost_sensitivity="medium",
        heat_sensitivity="medium",
    )


def test_crop_service_rejects_case_insensitive_duplicate_names(db):
    create_crop(db, _build_crop_schema("Wheat"))

    with pytest.raises(ConflictError, match="already exists"):
        create_crop(db, _build_crop_schema("WHEAT"))


def test_crop_service_rejects_duplicate_name_on_update(db):
    wheat = create_crop(db, _build_crop_schema("Wheat"))
    corn = create_crop(db, _build_crop_schema("Corn"))

    with pytest.raises(ConflictError, match="already exists"):
        update_crop(db, corn.id, CropProfileUpdate(crop_name="wheat"))

    assert wheat.crop_name == "Wheat"


def test_soil_service_rejects_missing_field_on_create(db):
    with pytest.raises(NotFoundError, match="Field with id 999 not found"):
        create_soil_test(
            db,
            SoilTestCreate(
                field_id=999,
                ph=6.5,
                nitrogen_ppm=45.0,
                phosphorus_ppm=30.0,
                potassium_ppm=200.0,
                organic_matter_percent=3.5,
                texture_class="loamy",
            ),
        )


def test_soil_service_rejects_missing_field_on_update(db):
    field = create_field(db, _build_field_schema("Service Field"))
    soil_test = create_soil_test(
        db,
        SoilTestCreate(
            field_id=field.id,
            ph=6.5,
            nitrogen_ppm=45.0,
            phosphorus_ppm=30.0,
            potassium_ppm=200.0,
            organic_matter_percent=3.5,
            texture_class="loamy",
        ),
    )

    with pytest.raises(NotFoundError, match="Field with id 999 not found"):
        update_soil_test(db, soil_test.id, SoilTestUpdate(field_id=999))


def test_dashboard_service_aggregates_live_data(db):
    field_alpha = create_field(db, _build_field_schema("Alpha"))
    field_beta = create_field(db, _build_field_schema("Beta"))
    create_crop(db, _build_crop_schema("Wheat"))
    create_crop(db, _build_crop_schema("Corn"))
    create_soil_test(
        db,
        SoilTestCreate(
            field_id=field_alpha.id,
            sample_date="2026-03-15T10:00:00Z",
            ph=6.4,
            nitrogen_ppm=40.0,
            phosphorus_ppm=24.0,
            potassium_ppm=175.0,
            organic_matter_percent=3.1,
            texture_class="loamy",
        ),
    )
    create_soil_test(
        db,
        SoilTestCreate(
            field_id=field_alpha.id,
            sample_date="2026-03-20T10:00:00Z",
            ph=6.6,
            nitrogen_ppm=46.0,
            phosphorus_ppm=30.0,
            potassium_ppm=205.0,
            organic_matter_percent=3.8,
            texture_class="clay loam",
        ),
    )

    overview = get_dashboard_overview(db)

    assert overview.totals.fields == 2
    assert overview.totals.soil_tests == 2
    assert overview.totals.crop_profiles == 2
    assert overview.coverage.fields_with_soil_tests == 1
    assert overview.coverage.fields_without_soil_tests == 1
    assert [item.name for item in overview.recent_fields] == ["Beta", "Alpha"]
    assert overview.recent_soil_tests[0].field_name == "Alpha"
    assert overview.recent_crop_profiles[0].crop_name == "Corn"
