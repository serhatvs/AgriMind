from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.crop_price import CropPrice
from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
)
from app.models.field import Field
from app.models.input_cost import InputCost
from app.models.soil_test import SoilTest
from app.schemas.feedback import (
    RecommendationResultInput,
    RecommendationRunLog,
    RecommendationRunRead,
    SeasonResultLog,
    SeasonResultRead,
    UserDecisionLog,
)
from app.services.feedback_service import log_recommendation, log_season_result, log_user_decision
from app.services.ranking_service import get_ranked_fields_response


def _create_field(db, name: str, **overrides) -> Field:
    values = {
        "name": name,
        "location_name": f"{name} Region",
        "latitude": 39.0,
        "longitude": -94.0,
        "area_hectares": 10.0,
        "slope_percent": 3.0,
        "irrigation_available": True,
        "drainage_quality": "good",
        "infrastructure_score": 70,
    }
    values.update(overrides)
    field = Field(**values)
    db.add(field)
    db.flush()
    return field


def _create_crop(db, **overrides) -> CropProfile:
    values = {
        "crop_name": "Corn",
        "scientific_name": "Zea mays",
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 6.8,
        "tolerable_ph_min": 5.8,
        "tolerable_ph_max": 7.2,
        "water_requirement_level": WaterRequirementLevel.MEDIUM,
        "drainage_requirement": CropDrainageRequirement.MODERATE,
        "frost_sensitivity": CropSensitivityLevel.HIGH,
        "heat_sensitivity": CropSensitivityLevel.MEDIUM,
        "salinity_tolerance": CropPreferenceLevel.MODERATE,
        "rooting_depth_cm": 120.0,
        "slope_tolerance": 8.0,
        "organic_matter_preference": CropPreferenceLevel.MODERATE,
        "crop_price": CropPrice(price_per_ton=210.0),
        "input_cost": InputCost(fertilizer_cost=240.0, water_cost=165.0, labor_cost=130.0),
    }
    values.update(overrides)
    crop = CropProfile(**values)
    db.add(crop)
    db.flush()
    return crop


def _create_soil(db, field_id: int, **overrides) -> SoilTest:
    values = {
        "field_id": field_id,
        "ph": 6.5,
        "ec": 1.0,
        "organic_matter_percent": 4.0,
        "nitrogen_ppm": 45.0,
        "phosphorus_ppm": 32.0,
        "potassium_ppm": 200.0,
        "texture_class": "loamy",
        "drainage_class": "good",
        "depth_cm": 120.0,
        "water_holding_capacity": 22.0,
    }
    values.update(overrides)
    soil_test = SoilTest(**values)
    db.add(soil_test)
    return soil_test


def _build_recommendation_log(crop_id: int, field_ids: list[int]) -> RecommendationRunLog:
    return RecommendationRunLog(
        crop_id=crop_id,
        results=[
            RecommendationResultInput(field_id=field_id, score=92.0 - index, rank=index + 1)
            for index, field_id in enumerate(field_ids)
        ],
    )


def test_log_recommendation_persists_run_and_results(db):
    crop = _create_crop(db)
    field_a = _create_field(db, "Alpha")
    field_b = _create_field(db, "Beta")
    db.commit()

    recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [field_a.id, field_b.id]))

    assert recommendation_run.id is not None
    assert recommendation_run.crop_id == crop.id
    assert [(entry.field_id, entry.rank) for entry in recommendation_run.results] == [
        (field_a.id, 1),
        (field_b.id, 2),
    ]

    serialized = RecommendationRunRead.model_validate(recommendation_run)
    assert serialized.results[0].score == 92.0


def test_log_recommendation_rejects_duplicate_field_ids():
    with pytest.raises(ValidationError, match="duplicate field_id"):
        RecommendationRunLog(
            crop_id=1,
            results=[
                RecommendationResultInput(field_id=3, score=88.0, rank=1),
                RecommendationResultInput(field_id=3, score=76.0, rank=2),
            ],
        )


def test_log_recommendation_rejects_duplicate_ranks():
    with pytest.raises(ValidationError, match="duplicate rank"):
        RecommendationRunLog(
            crop_id=1,
            results=[
                RecommendationResultInput(field_id=3, score=88.0, rank=1),
                RecommendationResultInput(field_id=4, score=76.0, rank=1),
            ],
        )


def test_log_recommendation_rejects_missing_crop(db):
    field_obj = _create_field(db, "Alpha")
    db.commit()

    with pytest.raises(ValueError, match="Crop with id 999 not found"):
        log_recommendation(db, _build_recommendation_log(999, [field_obj.id]))


def test_log_user_decision_rejects_duplicate_decision(db):
    crop = _create_crop(db)
    field_obj = _create_field(db, "Alpha")
    db.commit()
    recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [field_obj.id]))

    log_user_decision(
        db,
        UserDecisionLog(recommendation_run_id=recommendation_run.id, selected_field_id=field_obj.id),
    )

    with pytest.raises(ValueError, match="User decision already exists"):
        log_user_decision(
            db,
            UserDecisionLog(recommendation_run_id=recommendation_run.id, selected_field_id=field_obj.id),
        )


def test_log_user_decision_allows_existing_field_outside_recommendation_results(db):
    crop = _create_crop(db)
    recommended_field = _create_field(db, "Recommended")
    selected_field = _create_field(db, "Selected")
    db.commit()
    recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [recommended_field.id]))

    decision = log_user_decision(
        db,
        UserDecisionLog(recommendation_run_id=recommendation_run.id, selected_field_id=selected_field.id),
    )

    assert decision.selected_field_id == selected_field.id


@pytest.mark.parametrize(
    ("recommendation_run_id", "selected_field_id", "message"),
    [
        (999, 1, "Recommendation run with id 999 not found"),
        (1, 999, "Field with id 999 not found"),
    ],
)
def test_log_user_decision_rejects_missing_run_or_field(db, recommendation_run_id, selected_field_id, message):
    crop = _create_crop(db)
    field_obj = _create_field(db, "Alpha")
    db.commit()

    if recommendation_run_id == 1:
        recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [field_obj.id]))
        recommendation_run_id = recommendation_run.id

    with pytest.raises(ValueError, match=message):
        log_user_decision(
            db,
            UserDecisionLog(
                recommendation_run_id=recommendation_run_id,
                selected_field_id=selected_field_id,
            ),
        )


def test_log_season_result_rejects_duplicate_result(db):
    crop = _create_crop(db)
    field_obj = _create_field(db, "Alpha")
    db.commit()
    recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [field_obj.id]))
    log_user_decision(
        db,
        UserDecisionLog(recommendation_run_id=recommendation_run.id, selected_field_id=field_obj.id),
    )
    payload = SeasonResultLog.model_validate(
        {
            "recommendation_run_id": recommendation_run.id,
            "field_id": field_obj.id,
            "crop_id": crop.id,
            "yield": 8.6,
            "actual_cost": 1400.0,
            "notes": "",
        }
    )

    first_result = log_season_result(db, payload)
    serialized = SeasonResultRead.model_validate(first_result)

    assert serialized.notes is None
    assert serialized.model_dump(by_alias=True)["yield"] == 8.6

    with pytest.raises(ValueError, match="Season result already exists"):
        log_season_result(db, payload)


@pytest.mark.parametrize(
    ("recommendation_run_id", "field_id", "crop_id", "message"),
    [
        (999, 1, 1, "Recommendation run with id 999 not found"),
        (1, 999, 1, "Field with id 999 not found"),
        (1, 1, 999, "Crop with id 999 not found"),
    ],
)
def test_log_season_result_rejects_missing_run_field_or_crop(db, recommendation_run_id, field_id, crop_id, message):
    crop = _create_crop(db)
    field_obj = _create_field(db, "Alpha")
    db.commit()
    recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [field_obj.id]))
    log_user_decision(
        db,
        UserDecisionLog(recommendation_run_id=recommendation_run.id, selected_field_id=field_obj.id),
    )

    if recommendation_run_id == 1:
        recommendation_run_id = recommendation_run.id
    if field_id == 1:
        field_id = field_obj.id
    if crop_id == 1:
        crop_id = crop.id

    payload = SeasonResultLog(
        recommendation_run_id=recommendation_run_id,
        field_id=field_id,
        crop_id=crop_id,
        yield_amount=7.5,
        actual_cost=1200.0,
    )

    with pytest.raises(ValueError, match=message):
        log_season_result(db, payload)


def test_log_season_result_rejects_crop_mismatch(db):
    crop = _create_crop(db, crop_name="Corn")
    other_crop = _create_crop(db, crop_name="Soybean", scientific_name="Glycine max")
    field_obj = _create_field(db, "Alpha")
    db.commit()
    recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [field_obj.id]))
    log_user_decision(
        db,
        UserDecisionLog(recommendation_run_id=recommendation_run.id, selected_field_id=field_obj.id),
    )

    with pytest.raises(ValueError, match="crop_id must match"):
        log_season_result(
            db,
            SeasonResultLog(
                recommendation_run_id=recommendation_run.id,
                field_id=field_obj.id,
                crop_id=other_crop.id,
                yield_amount=7.9,
                actual_cost=1190.0,
            ),
        )


def test_log_season_result_rejects_field_mismatch_against_user_decision(db):
    crop = _create_crop(db)
    field_a = _create_field(db, "Alpha")
    field_b = _create_field(db, "Beta")
    db.commit()
    recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [field_a.id, field_b.id]))
    log_user_decision(
        db,
        UserDecisionLog(recommendation_run_id=recommendation_run.id, selected_field_id=field_a.id),
    )

    with pytest.raises(ValueError, match="field_id must match"):
        log_season_result(
            db,
            SeasonResultLog(
                recommendation_run_id=recommendation_run.id,
                field_id=field_b.id,
                crop_id=crop.id,
                yield_amount=7.9,
                actual_cost=1190.0,
            ),
        )


def test_log_season_result_requires_existing_user_decision(db):
    crop = _create_crop(db)
    field_obj = _create_field(db, "Alpha")
    db.commit()
    recommendation_run = log_recommendation(db, _build_recommendation_log(crop.id, [field_obj.id]))

    with pytest.raises(ValueError, match="user decision must be logged"):
        log_season_result(
            db,
            SeasonResultLog(
                recommendation_run_id=recommendation_run.id,
                field_id=field_obj.id,
                crop_id=crop.id,
                yield_amount=7.9,
                actual_cost=1190.0,
            ),
        )


def test_closed_loop_feedback_usage_with_ranking_response(db):
    crop = _create_crop(db)
    field_a = _create_field(db, "Field Alpha", drainage_quality="excellent")
    field_b = _create_field(db, "Field Beta", irrigation_available=False, slope_percent=9.0)
    db.commit()

    _create_soil(db, field_a.id, ph=6.4, depth_cm=140.0, ec=1.0)
    _create_soil(db, field_b.id, ph=5.4, depth_cm=85.0, ec=1.8, organic_matter_percent=2.2)
    db.commit()

    ranking = get_ranked_fields_response(db, crop_id=crop.id, field_ids=[field_a.id, field_b.id])

    recommendation_run = log_recommendation(
        db,
        RecommendationRunLog(
            crop_id=ranking.crop.id,
            results=[
                RecommendationResultInput(
                    field_id=item.field_id,
                    score=item.ranking_score,
                    rank=item.rank,
                )
                for item in ranking.ranked_results
            ],
        ),
    )
    user_decision = log_user_decision(
        db,
        UserDecisionLog(
            recommendation_run_id=recommendation_run.id,
            selected_field_id=ranking.ranked_results[0].field_id,
        ),
    )
    season_result = log_season_result(
        db,
        SeasonResultLog.model_validate(
            {
                "recommendation_run_id": recommendation_run.id,
                "field_id": user_decision.selected_field_id,
                "crop_id": ranking.crop.id,
                "yield": 9.1,
                "actual_cost": 1480.0,
                "notes": "Harvest completed with expected quality.",
            }
        ),
    )

    assert len(recommendation_run.results) == 2
    assert recommendation_run.results[0].score == ranking.ranked_results[0].ranking_score
    assert user_decision.selected_field_id == ranking.ranked_results[0].field_id
    assert season_result.yield_amount == 9.1
