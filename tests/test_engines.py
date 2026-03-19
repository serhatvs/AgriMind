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
    """Factory for creating a mock CropProfile object with sensible wheat defaults."""
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
    """Factory for creating a mock Field object with sensible defaults."""
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
    """Factory for creating a mock SoilTest object with adequate nutrient defaults."""
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
    """Test that a pH within the optimal range returns the full weight."""
    crop = make_crop()
    assert score_ph(6.5, crop, 25) == 25.0


def test_score_ph_acceptable():
    """Test that a pH in the acceptable (non-optimal) range returns 60% of the weight."""
    crop = make_crop()
    assert score_ph(5.8, crop, 25) == pytest.approx(15.0)


def test_score_ph_outside():
    """Test that a pH outside the acceptable range returns zero."""
    crop = make_crop()
    assert score_ph(4.0, crop, 25) == 0.0


def test_score_nutrient_full():
    """Test that a nutrient level at or above the minimum returns the full weight."""
    assert score_nutrient(50.0, 30.0, 15) == 15.0


def test_score_nutrient_proportional():
    """Test that a nutrient level below the minimum returns a proportional score."""
    assert score_nutrient(15.0, 30.0, 15) == pytest.approx(7.5)


def test_score_nutrient_zero_minimum():
    """Test that when the minimum requirement is zero, the full weight is always returned."""
    assert score_nutrient(0.0, 0.0, 10) == 10.0


def test_score_drainage_sufficient():
    """Test that drainage equal to or better than required returns the full weight."""
    assert score_drainage("good", "moderate", 15) == 15.0


def test_score_drainage_insufficient():
    """Test that drainage worse than required returns a partial score greater than zero."""
    result = score_drainage("poor", "good", 15)
    assert result < 15.0
    assert result > 0.0


def test_score_irrigation_available():
    """Test that irrigation available always yields the full weight regardless of crop requirement."""
    assert score_irrigation(True, "high", 10) == 10.0


def test_score_irrigation_low_requirement():
    """Test that a low water-requirement crop scores full points even without irrigation."""
    assert score_irrigation(False, "low", 10) == 10.0


def test_score_irrigation_no_irrigation_high():
    """Test that no irrigation combined with a high water requirement returns zero."""
    assert score_irrigation(False, "high", 10) == 0.0


def test_score_slope_within():
    """Test that a slope within the crop maximum returns the full weight."""
    assert score_slope(3.0, 10.0, 10) == 10.0


def test_score_slope_over():
    """Test that a slope slightly above the maximum returns a partial score."""
    result = score_slope(12.0, 10.0, 10)
    assert 0.0 < result < 10.0


def test_score_slope_double():
    """Test that a slope at double the maximum returns zero."""
    assert score_slope(20.0, 10.0, 10) == 0.0


def test_score_soil_texture_match():
    """Test that a matching soil texture returns the full weight."""
    assert score_soil_texture("loamy", "loamy,silty", 5) == 5.0


def test_score_soil_texture_no_match():
    """Test that a non-matching soil texture returns zero."""
    assert score_soil_texture("sandy", "loamy,silty", 5) == 0.0


def test_calculate_suitability_with_soil():
    """Test that a field with soil data receives a positive score with all components present."""
    field = make_field()
    crop = make_crop()
    soil = make_soil()
    result = calculate_suitability(field, crop, soil)
    assert 0 < result.total_score <= 100
    assert "ph_score" in result.component_scores


def test_calculate_suitability_no_soil():
    """Test that a field without soil data gets a minimal non-zero score and zero nutrient points."""
    field = make_field()
    crop = make_crop()
    result = calculate_suitability(field, crop, None)
    assert result.total_score >= 5.0
    assert result.component_scores["ph_score"] == 0.0
