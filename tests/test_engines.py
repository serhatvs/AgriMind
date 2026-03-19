from types import SimpleNamespace

from app.engines.suitability_engine import (
    calculate_suitability,
    normalize_total_score,
    score_drainage_compatibility,
    score_ph_compatibility,
    score_slope_compatibility,
    score_soil_compatibility,
    score_water_availability,
)
from app.engines.scoring_config import load_scoring_config


CONFIG = load_scoring_config()


def make_crop(**kwargs):
    """Create a lightweight crop profile test double with sensible defaults."""

    values = {
        "id": 1,
        "crop_name": "Wheat",
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 7.0,
        "tolerable_ph_min": 5.5,
        "tolerable_ph_max": 7.5,
        "water_requirement_level": "medium",
        "drainage_requirement": "good",
        "salinity_tolerance": "moderate",
        "rooting_depth_cm": 100.0,
        "slope_tolerance": 10.0,
        "organic_matter_preference": "moderate",
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def make_field(**kwargs):
    """Create a lightweight field test double with sensible defaults."""

    values = {
        "id": 1,
        "name": "North Parcel",
        "irrigation_available": True,
        "drainage_quality": "good",
        "slope_percent": 3.0,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def make_soil(**kwargs):
    """Create a lightweight soil test double with sensible defaults."""

    values = {
        "id": 1,
        "ph": 6.5,
        "organic_matter_percent": 4.0,
        "depth_cm": 120.0,
        "ec": 1.5,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_calculate_suitability_ideal_case_returns_high_score_with_positive_reasons():
    """Ideal field, soil, and crop inputs should produce a strong suitability score."""

    result = calculate_suitability(make_field(), make_crop(), make_soil())

    assert 80 <= result.total_score <= 100
    assert result.soil_test_id == 1
    assert not result.blockers
    assert "pH is within ideal range." in result.reasons
    assert "Field has irrigation available." in result.reasons
    assert result.score_breakdown["soil_compatibility"].awarded_points > 0


def test_no_irrigation_for_high_water_crop_returns_blocker_and_zero_score():
    """A high water-demand crop without irrigation should be blocked."""

    result = calculate_suitability(
        make_field(irrigation_available=False),
        make_crop(water_requirement_level="high"),
        make_soil(),
    )

    assert result.total_score == 0.0
    assert any(blocker.code == "no_irrigation_high_water_crop" for blocker in result.blockers)
    assert "No irrigation available for a high water-demand crop." in result.reasons


def test_ph_outside_tolerable_range_by_less_than_blocker_delta_does_not_block():
    """A mild pH miss should score poorly without becoming a blocker."""

    component = score_ph_compatibility(make_crop(), make_soil(ph=5.2), CONFIG)
    result = calculate_suitability(make_field(), make_crop(), make_soil(ph=5.2))

    assert component.awarded_points == 0.0
    assert not any(blocker.code == "ph_far_outside_tolerable_range" for blocker in result.blockers)
    assert "pH is outside the tolerable range." in component.reasons


def test_ph_outside_tolerable_range_by_blocker_delta_or_more_blocks():
    """A large pH mismatch should become a hard blocker."""

    result = calculate_suitability(make_field(), make_crop(), make_soil(ph=4.9))

    assert result.total_score == 0.0
    assert any(blocker.code == "ph_far_outside_tolerable_range" for blocker in result.blockers)
    assert "Soil pH is far outside the crop tolerable range." in result.reasons


def test_drainage_below_requirement_yields_partial_score_and_penalty():
    """Drainage shortfalls should reduce score and surface a penalty message."""

    component = score_drainage_compatibility(
        make_field(drainage_quality="poor"),
        make_crop(drainage_requirement="good"),
        CONFIG,
    )
    result = calculate_suitability(
        make_field(drainage_quality="poor"),
        make_crop(drainage_requirement="good"),
        make_soil(),
    )

    assert 0.0 < component.awarded_points < component.max_points
    assert any(penalty.dimension == "drainage_compatibility" for penalty in result.penalties)
    assert "Drainage is below crop requirement." in component.reasons


def test_shallow_soil_depth_reduces_soil_compatibility():
    """Rooting depth mismatches should reduce the soil compatibility dimension."""

    component = score_soil_compatibility(
        make_crop(rooting_depth_cm=120.0),
        make_soil(depth_cm=70.0),
        CONFIG,
    )

    assert component.awarded_points < component.max_points
    assert "Soil depth is below the crop rooting requirement." in component.reasons


def test_high_ec_against_low_salinity_tolerance_reduces_soil_compatibility():
    """Excess salinity should reduce the soil compatibility score for sensitive crops."""

    component = score_soil_compatibility(
        make_crop(salinity_tolerance="low"),
        make_soil(ec=3.0),
        CONFIG,
    )

    assert component.awarded_points < component.max_points
    assert "Soil salinity exceeds the crop tolerance." in component.reasons


def test_slope_above_tolerance_reduces_slope_score():
    """Slope beyond the crop threshold should award only a partial score."""

    component = score_slope_compatibility(
        make_field(slope_percent=12.0),
        make_crop(slope_tolerance=10.0),
        CONFIG,
    )

    assert 0.0 < component.awarded_points < component.max_points
    assert "Field slope exceeds the crop tolerance." in component.reasons


def test_missing_soil_test_returns_blocker_and_zero_score():
    """Missing soil data should hard-block the MVP suitability calculation."""

    result = calculate_suitability(make_field(), make_crop(), None)

    assert result.total_score == 0.0
    assert any(blocker.code == "missing_soil_test" for blocker in result.blockers)
    assert "No soil test available for suitability scoring." in result.reasons


def test_score_normalization_is_clamped_to_zero_and_hundred():
    """Normalization should never return values outside the 0-100 range."""

    assert normalize_total_score(130.0, 100.0) == 100.0
    assert normalize_total_score(-10.0, 100.0) == 0.0


def test_water_availability_helper_reports_irrigation_reason():
    """Water scoring should emit the canonical irrigation reason when irrigation exists."""

    component = score_water_availability(make_field(irrigation_available=True), make_crop(), CONFIG)

    assert component.awarded_points == component.max_points
    assert component.reasons == ["Field has irrigation available."]
