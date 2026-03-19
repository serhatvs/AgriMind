from types import SimpleNamespace

from app.engines.explanation_engine import (
    build_ranked_field_explanation,
    build_suitability_explanation,
    generate_explanation,
)
from app.engines.ranking_engine import rank_fields_for_crop
from app.engines.suitability_engine import calculate_suitability


def make_crop(**kwargs):
    values = {
        "id": 1,
        "crop_name": "Corn",
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 6.8,
        "tolerable_ph_min": 5.8,
        "tolerable_ph_max": 7.0,
        "water_requirement_level": "medium",
        "drainage_requirement": "moderate",
        "salinity_tolerance": "moderate",
        "rooting_depth_cm": 100.0,
        "slope_tolerance": 10.0,
        "organic_matter_preference": "moderate",
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def make_field(**kwargs):
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
    values = {
        "id": 1,
        "ph": 6.5,
        "organic_matter_percent": 4.0,
        "depth_cm": 120.0,
        "ec": 1.5,
    }
    values.update(kwargs)
    return SimpleNamespace(**values)


def test_ranked_field_explanation_surfaces_positive_strengths():
    field_obj = make_field()
    crop = make_crop()
    soil_map = {field_obj.id: make_soil()}

    ranked = rank_fields_for_crop([field_obj], crop, soil_map)
    explanation = build_ranked_field_explanation(ranked.ranked_fields[0])

    assert "ranked highly" in explanation.short_explanation.lower()
    assert "pH is within ideal range." in explanation.strengths
    assert "Field has irrigation available." in explanation.strengths
    assert "Strengths:" in explanation.detailed_explanation
    assert explanation.risks == []


def test_explanation_collects_weaknesses_from_penalties():
    field_obj = make_field(drainage_quality="poor", slope_percent=15.0)
    crop = make_crop(drainage_requirement="good", slope_tolerance=10.0)
    soil_map = {field_obj.id: make_soil()}

    ranked = rank_fields_for_crop([field_obj], crop, soil_map)
    explanation = build_ranked_field_explanation(ranked.ranked_fields[0])

    assert "Drainage is below crop requirement." in explanation.weaknesses
    assert "Field slope exceeds the crop tolerance." in explanation.weaknesses
    assert "Weaknesses:" in explanation.detailed_explanation
    assert "Drainage is below crop requirement." in explanation.detailed_explanation


def test_blocked_result_surfaces_risks_and_negative_short_explanation():
    field_obj = make_field(irrigation_available=False)
    crop = make_crop(water_requirement_level="high")
    soil_map = {field_obj.id: make_soil()}

    ranked = rank_fields_for_crop([field_obj], crop, soil_map)
    explanation = build_ranked_field_explanation(ranked.ranked_fields[0])

    assert "No irrigation available for a high water-demand crop." in explanation.risks
    assert "not suitable because" in explanation.short_explanation.lower()
    assert "Blockers:" in explanation.detailed_explanation


def test_missing_soil_data_becomes_a_risk_without_crashing():
    field_obj = make_field()
    crop = make_crop()
    result = calculate_suitability(field_obj, crop, None)

    explanation = build_suitability_explanation(result, field_obj)

    assert "No soil test available for suitability scoring." in explanation.risks
    assert explanation.short_explanation.startswith("This field is not suitable")


def test_ranked_and_suitability_adapters_produce_equivalent_explanations():
    field_obj = make_field()
    crop = make_crop()
    soil = make_soil()
    result = calculate_suitability(field_obj, crop, soil)
    ranked = rank_fields_for_crop([field_obj], crop, {field_obj.id: soil})

    from_ranked = build_ranked_field_explanation(ranked.ranked_fields[0])
    from_suitability = build_suitability_explanation(result, field_obj)

    assert from_ranked.model_dump() == from_suitability.model_dump()


def test_generate_explanation_returns_legacy_detailed_string():
    field_obj = make_field(irrigation_available=False)
    crop = make_crop(water_requirement_level="high")
    result = calculate_suitability(field_obj, crop, make_soil())

    explanation = generate_explanation(result, field_obj, crop)

    assert explanation == build_suitability_explanation(result, field_obj).detailed_explanation
    assert "Field 'North Parcel'" in explanation
    assert "Blockers:" in explanation
