import pytest
from pydantic import ValidationError

from app.schemas.soil_test import SoilTestCreate


def test_soil_test_create_requires_core_fields():
    """Test that required soil test fields remain mandatory."""
    with pytest.raises(ValidationError):
        SoilTestCreate(
            field_id=1,
            ph=6.5,
            organic_matter_percent=3.5,
            nitrogen_ppm=45.0,
            phosphorus_ppm=30.0,
            potassium_ppm=200.0,
        )


def test_soil_test_create_accepts_legacy_aliases():
    """Test that legacy soil aliases map onto canonical field names."""
    soil_test = SoilTestCreate(
        field_id=1,
        tested_at="2026-03-15T10:00:00Z",
        ph_level=6.5,
        organic_matter_percent=3.5,
        nitrogen_ppm=45.0,
        phosphorus_ppm=30.0,
        potassium_ppm=200.0,
        soil_texture="loamy",
    )

    assert soil_test.ph == 6.5
    assert soil_test.texture_class == "loamy"
    assert soil_test.sample_date.isoformat().startswith("2026-03-15T10:00:00")


def test_soil_test_create_rejects_invalid_ph():
    """Test that pH values outside the supported range are rejected."""
    with pytest.raises(ValidationError):
        SoilTestCreate(
            field_id=1,
            ph=18.0,
            organic_matter_percent=3.5,
            nitrogen_ppm=45.0,
            phosphorus_ppm=30.0,
            potassium_ppm=200.0,
            texture_class="loamy",
        )


def test_soil_test_create_rejects_negative_optional_metrics():
    """Test that optional measured values still enforce non-negative ranges."""
    with pytest.raises(ValidationError):
        SoilTestCreate(
            field_id=1,
            ph=6.5,
            ec=-0.1,
            organic_matter_percent=3.5,
            nitrogen_ppm=45.0,
            phosphorus_ppm=30.0,
            potassium_ppm=200.0,
            texture_class="loamy",
        )
