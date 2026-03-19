from datetime import datetime, timedelta, timezone

import pytest

from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
)
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.services.ranking_service import get_ranked_fields_response


def make_crop(**kwargs) -> CropProfile:
    values = {
        "crop_name": "Corn",
        "scientific_name": "Zea mays",
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 6.8,
        "tolerable_ph_min": 5.8,
        "tolerable_ph_max": 7.0,
        "water_requirement_level": WaterRequirementLevel.MEDIUM,
        "drainage_requirement": CropDrainageRequirement.MODERATE,
        "frost_sensitivity": CropSensitivityLevel.HIGH,
        "heat_sensitivity": CropSensitivityLevel.MEDIUM,
        "salinity_tolerance": CropPreferenceLevel.MODERATE,
        "rooting_depth_cm": 120.0,
        "slope_tolerance": 8.0,
        "organic_matter_preference": CropPreferenceLevel.MODERATE,
    }
    values.update(kwargs)
    return CropProfile(**values)


def make_field(name: str, **kwargs) -> Field:
    values = {
        "name": name,
        "location_name": f"{name} Zone",
        "latitude": 39.0,
        "longitude": -94.0,
        "area_hectares": 10.0,
        "slope_percent": 3.0,
        "irrigation_available": True,
        "drainage_quality": "good",
    }
    values.update(kwargs)
    return Field(**values)


def make_soil(field_id: int, **kwargs) -> SoilTest:
    values = {
        "field_id": field_id,
        "ph": 6.5,
        "organic_matter_percent": 4.0,
        "nitrogen_ppm": 50.0,
        "phosphorus_ppm": 35.0,
        "potassium_ppm": 220.0,
        "texture_class": "loamy",
        "depth_cm": 120.0,
        "ec": 1.2,
    }
    values.update(kwargs)
    return SoilTest(**values)


def test_get_ranked_fields_response_ranks_all_fields_when_no_filter(db):
    crop = make_crop()
    field_a = make_field("Field Alpha", drainage_quality="excellent")
    field_b = make_field("Field Beta", irrigation_available=False, slope_percent=9.0)
    db.add_all([crop, field_a, field_b])
    db.commit()

    db.add_all([
        make_soil(field_a.id, ph=6.4, depth_cm=140.0, ec=1.0),
        make_soil(field_b.id, ph=5.1, depth_cm=60.0, ec=3.0, organic_matter_percent=1.0),
    ])
    db.commit()

    response = get_ranked_fields_response(db, crop_id=crop.id)

    assert response.total_fields_evaluated == 2
    assert response.crop.crop_name == "Corn"
    assert len(response.ranked_results) == 2
    assert response.ranked_results[0].field_name == "Field Alpha"
    assert response.ranked_results[0].explanation.short_explanation


def test_get_ranked_fields_response_respects_field_filter(db):
    crop = make_crop()
    field_a = make_field("Field Alpha")
    field_b = make_field("Field Beta")
    db.add_all([crop, field_a, field_b])
    db.commit()

    db.add_all([
        make_soil(field_a.id),
        make_soil(field_b.id),
    ])
    db.commit()

    response = get_ranked_fields_response(db, crop_id=crop.id, field_ids=[field_b.id])

    assert response.total_fields_evaluated == 1
    assert [entry.field_id for entry in response.ranked_results] == [field_b.id]


def test_get_ranked_fields_response_uses_latest_soil_test(db):
    crop = make_crop()
    field_obj = make_field("Field Alpha")
    db.add_all([crop, field_obj])
    db.commit()

    older_sample = datetime.now(timezone.utc) - timedelta(days=10)
    newer_sample = datetime.now(timezone.utc)
    db.add_all([
        make_soil(field_obj.id, ph=6.4, sample_date=older_sample),
        make_soil(field_obj.id, ph=4.9, sample_date=newer_sample),
    ])
    db.commit()

    response = get_ranked_fields_response(db, crop_id=crop.id, field_ids=[field_obj.id])

    assert response.ranked_results[0].total_score == 0.0
    assert any(
        blocker.code == "ph_far_outside_tolerable_range"
        for blocker in response.ranked_results[0].blockers
    )


def test_get_ranked_fields_response_raises_when_no_fields_found(db):
    crop = make_crop()
    db.add(crop)
    db.commit()

    with pytest.raises(ValueError, match="No fields found for ranking"):
        get_ranked_fields_response(db, crop_id=crop.id)
