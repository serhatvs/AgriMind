from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.crop_price import CropPrice
from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
    WaterSourceType,
)
from app.models.field import Field
from app.models.field_crop_cycle import FieldCropCycle
from app.models.input_cost import InputCost
from app.models.soil_test import SoilTest
from app.models.weather_history import WeatherHistory
from app.models.feedback import RecommendationResult, RecommendationRun, SeasonResult, UserDecision


def test_field_soil_test_relationship_and_crop_profile_persist_together(db):
    """Field, soil, and crop records should coexist cleanly in one ranking session."""

    field = Field(
        name="Model Parcel",
        location_name="Model Valley",
        latitude=39.1012,
        longitude=-94.5788,
        area_hectares=12.5,
        elevation_meters=210.0,
        slope_percent=2.5,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=78,
        drainage_quality="good",
    )
    crop = CropProfile(
        crop_name="Corn",
        scientific_name="Zea mays",
        ideal_ph_min=6.0,
        ideal_ph_max=6.8,
        tolerable_ph_min=5.8,
        tolerable_ph_max=7.2,
        water_requirement_level=WaterRequirementLevel.HIGH,
        drainage_requirement=CropDrainageRequirement.MODERATE,
        frost_sensitivity=CropSensitivityLevel.HIGH,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        salinity_tolerance=CropPreferenceLevel.MODERATE,
        rooting_depth_cm=150.0,
        slope_tolerance=6.0,
        organic_matter_preference=CropPreferenceLevel.MODERATE,
        crop_price=CropPrice(price_per_ton=210.0),
        input_cost=InputCost(fertilizer_cost=240.0, water_cost=165.0, labor_cost=130.0),
    )
    db.add_all([field, crop])
    db.flush()

    soil_test = SoilTest(
        field_id=field.id,
        sample_date=datetime(2026, 3, 15, 10, 0, tzinfo=timezone.utc),
        ph=6.4,
        ec=0.9,
        organic_matter_percent=3.8,
        nitrogen_ppm=42.0,
        phosphorus_ppm=28.0,
        potassium_ppm=210.0,
        calcium_ppm=1650.0,
        magnesium_ppm=215.0,
        texture_class="loamy",
        drainage_class="good",
        depth_cm=120.0,
        water_holding_capacity=22.0,
    )
    db.add(soil_test)
    db.commit()
    db.expire_all()

    persisted_field = db.query(Field).filter(Field.id == field.id).first()
    persisted_soil = db.query(SoilTest).filter(SoilTest.id == soil_test.id).first()
    persisted_crop = db.query(CropProfile).filter(CropProfile.id == crop.id).first()

    assert persisted_field is not None
    assert persisted_soil is not None
    assert persisted_crop is not None
    assert len(persisted_field.soil_tests) == 1
    assert persisted_field.soil_tests[0].id == persisted_soil.id
    assert persisted_soil.field is not None
    assert persisted_soil.field.id == persisted_field.id
    assert persisted_crop.crop_name == "Corn"
    assert persisted_crop.crop_price is not None
    assert persisted_crop.crop_price.price_per_ton == 210.0
    assert persisted_crop.input_cost is not None
    assert persisted_crop.input_cost.water_cost == 165.0


def test_field_weather_history_relationship_and_unique_daily_record(db):
    """Field weather rows should relate back to the field and enforce one row per day."""

    field = Field(
        name="Weather Parcel",
        location_name="Weather Valley",
        latitude=39.1012,
        longitude=-94.5788,
        area_hectares=12.5,
        elevation_meters=210.0,
        slope_percent=2.5,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=78,
        drainage_quality="good",
    )
    db.add(field)
    db.flush()

    weather_record = WeatherHistory(
        field_id=field.id,
        date=date(2026, 3, 19),
        min_temp=8.0,
        max_temp=20.0,
        avg_temp=14.0,
        rainfall_mm=5.0,
        humidity=62.0,
        wind_speed=12.0,
        solar_radiation=18.0,
        et0=3.4,
    )
    db.add(weather_record)
    db.commit()
    db.expire_all()

    persisted_field = db.query(Field).filter(Field.id == field.id).first()
    persisted_weather = db.query(WeatherHistory).filter(WeatherHistory.id == weather_record.id).first()

    assert persisted_field is not None
    assert persisted_weather is not None
    assert len(persisted_field.weather_history) == 1
    assert persisted_field.weather_history[0].id == persisted_weather.id
    assert persisted_weather.field is not None
    assert persisted_weather.field.id == persisted_field.id

    duplicate_weather = WeatherHistory(
        field_id=field.id,
        date=date(2026, 3, 19),
        min_temp=7.0,
        max_temp=18.0,
        avg_temp=12.0,
        rainfall_mm=1.0,
        humidity=58.0,
        wind_speed=10.0,
    )
    db.add(duplicate_weather)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_field_crop_cycle_relationships_persist_between_field_and_crop(db):
    """Field crop cycles should relate to both the owning field and crop profile."""

    field = Field(
        name="Lifecycle Parcel",
        location_name="Lifecycle Valley",
        latitude=39.1012,
        longitude=-94.5788,
        area_hectares=8.0,
        elevation_meters=215.0,
        slope_percent=1.5,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=82,
        drainage_quality="good",
    )
    crop = CropProfile(
        crop_name="Wheat",
        scientific_name="Triticum aestivum",
        ideal_ph_min=6.0,
        ideal_ph_max=7.0,
        tolerable_ph_min=5.5,
        tolerable_ph_max=7.5,
        water_requirement_level=WaterRequirementLevel.MEDIUM,
        drainage_requirement=CropDrainageRequirement.GOOD,
        frost_sensitivity=CropSensitivityLevel.MEDIUM,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        growth_stages=[
            {
                "name": "germination",
                "duration_days": 7,
                "irrigation_need": "medium",
                "fertilizer_need": "low",
            },
            {
                "name": "vegetative",
                "duration_days": 21,
                "irrigation_need": "high",
                "fertilizer_need": "medium",
            },
        ],
    )
    cycle = FieldCropCycle(
        field=field,
        crop=crop,
        sowing_date=date(2026, 3, 1),
        current_stage="germination",
    )

    db.add_all([field, crop, cycle])
    db.commit()
    db.expire_all()

    persisted_field = db.query(Field).filter(Field.id == field.id).first()
    persisted_crop = db.query(CropProfile).filter(CropProfile.id == crop.id).first()
    persisted_cycle = db.query(FieldCropCycle).filter(FieldCropCycle.id == cycle.id).first()

    assert persisted_field is not None
    assert persisted_crop is not None
    assert persisted_cycle is not None
    assert persisted_field.crop_cycle is not None
    assert persisted_field.crop_cycle.id == persisted_cycle.id
    assert persisted_crop.field_crop_cycles[0].id == persisted_cycle.id
    assert persisted_cycle.field.id == persisted_field.id
    assert persisted_cycle.crop.id == persisted_crop.id


def test_field_crop_cycle_enforces_one_active_cycle_per_field(db):
    """Only one active crop cycle should be allowed per field."""

    field = Field(
        name="Unique Cycle Parcel",
        location_name="Unique Cycle Valley",
        latitude=39.1012,
        longitude=-94.5788,
        area_hectares=8.0,
        elevation_meters=215.0,
        slope_percent=1.5,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=82,
        drainage_quality="good",
    )
    wheat = CropProfile(
        crop_name="Wheat",
        ideal_ph_min=6.0,
        ideal_ph_max=7.0,
        tolerable_ph_min=5.5,
        tolerable_ph_max=7.5,
        water_requirement_level=WaterRequirementLevel.MEDIUM,
        drainage_requirement=CropDrainageRequirement.GOOD,
        frost_sensitivity=CropSensitivityLevel.MEDIUM,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        growth_stages=[
            {
                "name": "germination",
                "duration_days": 7,
                "irrigation_need": "medium",
                "fertilizer_need": "low",
            }
        ],
    )
    corn = CropProfile(
        crop_name="Corn",
        ideal_ph_min=6.0,
        ideal_ph_max=6.8,
        tolerable_ph_min=5.8,
        tolerable_ph_max=7.2,
        water_requirement_level=WaterRequirementLevel.HIGH,
        drainage_requirement=CropDrainageRequirement.MODERATE,
        frost_sensitivity=CropSensitivityLevel.HIGH,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        growth_stages=[
            {
                "name": "vegetative",
                "duration_days": 21,
                "irrigation_need": "high",
                "fertilizer_need": "medium",
            }
        ],
    )

    db.add_all([field, wheat, corn])
    db.flush()
    db.add(
        FieldCropCycle(
            field_id=field.id,
            crop_id=wheat.id,
            sowing_date=date(2026, 3, 1),
            current_stage="germination",
        )
    )
    db.commit()

    db.add(
        FieldCropCycle(
            field_id=field.id,
            crop_id=corn.id,
            sowing_date=date(2026, 3, 15),
            current_stage="vegetative",
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_recommendation_feedback_relationships_persist_cleanly(db):
    """Recommendation runs should link ranked results, a user decision, and a season outcome."""

    crop = CropProfile(
        crop_name="Corn",
        scientific_name="Zea mays",
        ideal_ph_min=6.0,
        ideal_ph_max=6.8,
        tolerable_ph_min=5.8,
        tolerable_ph_max=7.2,
        water_requirement_level=WaterRequirementLevel.HIGH,
        drainage_requirement=CropDrainageRequirement.MODERATE,
        frost_sensitivity=CropSensitivityLevel.HIGH,
        heat_sensitivity=CropSensitivityLevel.MEDIUM,
        salinity_tolerance=CropPreferenceLevel.MODERATE,
        rooting_depth_cm=150.0,
        slope_tolerance=6.0,
        organic_matter_preference=CropPreferenceLevel.MODERATE,
        crop_price=CropPrice(price_per_ton=210.0),
        input_cost=InputCost(fertilizer_cost=240.0, water_cost=165.0, labor_cost=130.0),
    )
    field_a = Field(
        name="Feedback Alpha",
        location_name="Feedback Valley",
        latitude=39.1012,
        longitude=-94.5788,
        area_hectares=12.5,
        elevation_meters=210.0,
        slope_percent=2.5,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=78,
        drainage_quality="good",
    )
    field_b = Field(
        name="Feedback Beta",
        location_name="Feedback Valley",
        latitude=39.2012,
        longitude=-94.4788,
        area_hectares=9.5,
        elevation_meters=205.0,
        slope_percent=3.5,
        irrigation_available=True,
        water_source_type=WaterSourceType.WELL,
        infrastructure_score=75,
        drainage_quality="moderate",
    )
    db.add_all([crop, field_a, field_b])
    db.flush()

    recommendation_run = RecommendationRun(
        crop_id=crop.id,
        results=[
            RecommendationResult(field_id=field_a.id, score=91.5, rank=1),
            RecommendationResult(field_id=field_b.id, score=82.0, rank=2),
        ],
        user_decision=UserDecision(selected_field_id=field_b.id),
        season_result=SeasonResult(
            field_id=field_b.id,
            crop_id=crop.id,
            yield_amount=8.7,
            actual_cost=1390.0,
            notes="Observed after harvest.",
        ),
    )
    db.add(recommendation_run)
    db.commit()
    db.expire_all()

    persisted_run = db.query(RecommendationRun).filter(RecommendationRun.id == recommendation_run.id).first()
    persisted_field = db.query(Field).filter(Field.id == field_b.id).first()
    persisted_crop = db.query(CropProfile).filter(CropProfile.id == crop.id).first()

    assert persisted_run is not None
    assert persisted_field is not None
    assert persisted_crop is not None
    assert [result.rank for result in persisted_run.results] == [1, 2]
    assert persisted_run.user_decision is not None
    assert persisted_run.user_decision.selected_field_id == field_b.id
    assert persisted_run.season_result is not None
    assert persisted_run.season_result.field_id == field_b.id
    assert persisted_run.season_result.crop_id == crop.id
    assert persisted_field.user_decisions[0].recommendation_run_id == persisted_run.id
    assert persisted_field.season_results[0].recommendation_run_id == persisted_run.id
    assert persisted_crop.recommendation_runs[0].id == persisted_run.id
    assert persisted_crop.season_results[0].recommendation_run_id == persisted_run.id
