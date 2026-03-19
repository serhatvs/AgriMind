import pytest
from unittest.mock import MagicMock
from app.engines.suitability_engine import (
    calculate_suitability,
    score_ph,
    score_nutrient,
    score_drainage,
    score_irrigation,
    score_slope,
    score_soil_texture,
)


def make_crop(**kwargs):
    crop = MagicMock()
    crop.id = 1
    crop.name = "Wheat"
    crop.min_ph = 5.5
    crop.max_ph = 7.5
    crop.optimal_ph_min = 6.0
    crop.optimal_ph_max = 7.0
    crop.min_nitrogen_ppm = 30.0
    crop.min_phosphorus_ppm = 20.0
    crop.min_potassium_ppm = 150.0
    crop.water_requirement = "medium"
    crop.drainage_requirement = "good"
    crop.preferred_soil_textures = "loamy,silty"
    crop.min_area_hectares = 1.0
    crop.max_slope_percent = 10.0
    for k, v in kwargs.items():
        setattr(crop, k, v)
    return crop


def make_field(**kwargs):
    field = MagicMock()
    field.id = 1
    field.name = "Test"
    field.irrigation_available = True
    field.drainage_quality = "good"
    field.slope_percent = 3.0
    for k, v in kwargs.items():
        setattr(field, k, v)
    return field


def make_soil(**kwargs):
    soil = MagicMock()
    soil.ph_level = 6.5
    soil.nitrogen_ppm = 45.0
    soil.phosphorus_ppm = 30.0
    soil.potassium_ppm = 200.0
    soil.soil_texture = "loamy"
    for k, v in kwargs.items():
        setattr(soil, k, v)
    return soil


def test_score_ph_optimal():
    crop = make_crop()
    assert score_ph(6.5, crop, 25) == 25.0


def test_score_ph_acceptable():
    crop = make_crop()
    assert score_ph(5.8, crop, 25) == pytest.approx(15.0)


def test_score_ph_outside():
    crop = make_crop()
    assert score_ph(4.0, crop, 25) == 0.0


def test_score_nutrient_full():
    assert score_nutrient(50.0, 30.0, 15) == 15.0


def test_score_nutrient_proportional():
    assert score_nutrient(15.0, 30.0, 15) == pytest.approx(7.5)


def test_score_nutrient_zero_minimum():
    assert score_nutrient(0.0, 0.0, 10) == 10.0


def test_score_drainage_sufficient():
    assert score_drainage("good", "moderate", 15) == 15.0


def test_score_drainage_insufficient():
    result = score_drainage("poor", "good", 15)
    assert result < 15.0
    assert result > 0.0


def test_score_irrigation_available():
    assert score_irrigation(True, "high", 10) == 10.0


def test_score_irrigation_low_requirement():
    assert score_irrigation(False, "low", 10) == 10.0


def test_score_irrigation_no_irrigation_high():
    assert score_irrigation(False, "high", 10) == 0.0


def test_score_slope_within():
    assert score_slope(3.0, 10.0, 10) == 10.0


def test_score_slope_over():
    result = score_slope(12.0, 10.0, 10)
    assert 0.0 < result < 10.0


def test_score_slope_double():
    assert score_slope(20.0, 10.0, 10) == 0.0


def test_score_soil_texture_match():
    assert score_soil_texture("loamy", "loamy,silty", 5) == 5.0


def test_score_soil_texture_no_match():
    assert score_soil_texture("sandy", "loamy,silty", 5) == 0.0


def test_calculate_suitability_with_soil():
    field = make_field()
    crop = make_crop()
    soil = make_soil()
    result = calculate_suitability(field, crop, soil)
    assert 0 < result.total_score <= 100
    assert "ph_score" in result.component_scores


def test_calculate_suitability_no_soil():
    field = make_field()
    crop = make_crop()
    result = calculate_suitability(field, crop, None)
    assert result.total_score >= 5.0
    assert result.component_scores["ph_score"] == 0.0
