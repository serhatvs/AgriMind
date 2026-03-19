import pytest
from pydantic import ValidationError

from app.models.enums import FieldAspect, WaterSourceType
from app.schemas.field import FieldCreate, FieldUpdate


def test_field_create_requires_core_fields():
    """Test that the required create-time fields remain mandatory."""
    with pytest.raises(ValidationError):
        FieldCreate(
            name="North Parcel",
            location_name="Region A",
            latitude=12.5,
            longitude=18.2,
        )


def test_field_create_accepts_legacy_location_alias():
    """Test that location still populates location_name during validation."""
    field = FieldCreate(
        name="North Parcel",
        location="Region A",
        latitude=12.5,
        longitude=18.2,
        area_hectares=5.0,
    )

    assert field.location_name == "Region A"


def test_field_create_rejects_invalid_enum_values():
    """Test that unsupported enum values are rejected."""
    with pytest.raises(ValidationError):
        FieldCreate(
            name="North Parcel",
            location_name="Region A",
            latitude=12.5,
            longitude=18.2,
            area_hectares=5.0,
            aspect="uphill",
        )


def test_field_update_rejects_out_of_range_values():
    """Test that invalid numeric ranges are rejected on partial updates."""
    with pytest.raises(ValidationError):
        FieldUpdate(latitude=120.0)


def test_field_update_parses_declared_enums():
    """Test that supported enum values are converted into shared enum types."""
    update = FieldUpdate(aspect="south", water_source_type="well")

    assert update.aspect is FieldAspect.SOUTH
    assert update.water_source_type is WaterSourceType.WELL
