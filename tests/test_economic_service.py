from app.models.crop_price import CropPrice
from app.models.crop_profile import CropProfile
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    FieldAspect,
    WaterRequirementLevel,
    WaterSourceType,
)
from app.models.field import Field
from app.models.input_cost import InputCost
from app.schemas.yield_prediction import YieldPredictionRange, YieldPredictionResult
from app.services.economic_service import EconomicService
from app.services.yield_prediction_service import YieldPredictionService


def _build_field(irrigation_available: bool = True) -> Field:
    return Field(
        name="Economic Field",
        location_name="Economic Valley",
        latitude=39.0,
        longitude=-94.0,
        area_hectares=20.0,
        elevation_meters=210.0,
        slope_percent=2.0,
        aspect=FieldAspect.SOUTH,
        irrigation_available=irrigation_available,
        water_source_type=WaterSourceType.WELL if irrigation_available else WaterSourceType.NONE,
        infrastructure_score=70,
        drainage_quality="good",
    )


def _build_crop() -> CropProfile:
    return CropProfile(
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
        slope_tolerance=8.0,
        organic_matter_preference=CropPreferenceLevel.MODERATE,
        crop_price=CropPrice(price_per_ton=210.0),
        input_cost=InputCost(fertilizer_cost=240.0, water_cost=165.0, labor_cost=130.0),
    )


def _yield_prediction(field_id: int, crop_id: int, yield_per_hectare: float) -> YieldPredictionResult:
    return YieldPredictionResult(
        field_id=field_id,
        crop_id=crop_id,
        predicted_yield_per_hectare=yield_per_hectare,
        predicted_yield_range=YieldPredictionRange(min=max(0.0, yield_per_hectare - 1.0), max=yield_per_hectare + 1.0),
        confidence_score=0.82,
        model_version="yield-xgb-v1",
        training_source="test",
        feature_snapshot={},
    )


def test_economic_service_estimates_revenue_and_cost(db, tmp_path):
    field = _build_field(irrigation_available=True)
    crop = _build_crop()
    db.add_all([field, crop])
    db.commit()

    service = EconomicService(
        db,
        yield_prediction_service=YieldPredictionService(db, model_dir=tmp_path / "yield_model"),
    )

    revenue = service.estimate_revenue(8.0, 210.0, field.area_hectares)
    cost = service.estimate_cost(field, crop)

    assert revenue == 33600.0
    assert cost == 10700.0


def test_economic_service_skips_water_cost_without_irrigation(db, tmp_path):
    field = _build_field(irrigation_available=False)
    crop = _build_crop()
    db.add_all([field, crop])
    db.commit()

    service = EconomicService(
        db,
        yield_prediction_service=YieldPredictionService(db, model_dir=tmp_path / "yield_model"),
    )

    assert service.estimate_cost(field, crop) == 7400.0


def test_economic_service_calculates_profit_and_reasons(db, tmp_path):
    field = _build_field(irrigation_available=True)
    crop = _build_crop()
    db.add_all([field, crop])
    db.commit()

    service = EconomicService(
        db,
        yield_prediction_service=YieldPredictionService(db, model_dir=tmp_path / "yield_model"),
    )
    assessment = service.calculate_profit(
        field,
        crop,
        yield_prediction=_yield_prediction(field.id, crop.id, 9.0),
    )

    assert assessment.estimated_revenue == 37800.0
    assert assessment.estimated_cost == 10700.0
    assert assessment.estimated_profit == 27100.0
    assert "High profit due to high yield and low cost." in assessment.strengths


def test_economic_service_reports_irrigation_cost_pressure(db, tmp_path):
    field = _build_field(irrigation_available=True)
    crop = _build_crop()
    crop.input_cost.water_cost = 720.0
    db.add_all([field, crop])
    db.commit()

    service = EconomicService(
        db,
        yield_prediction_service=YieldPredictionService(db, model_dir=tmp_path / "yield_model"),
    )
    assessment = service.calculate_profit(
        field,
        crop,
        yield_prediction=_yield_prediction(field.id, crop.id, 1.1),
    )

    assert assessment.estimated_profit is not None
    assert assessment.estimated_profit < 0
    assert "Low profitability due to irrigation cost." in assessment.weaknesses


def test_economic_service_handles_missing_crop_economics(db, tmp_path):
    field = _build_field()
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
        salinity_tolerance=CropPreferenceLevel.LOW,
        rooting_depth_cm=120.0,
        slope_tolerance=10.0,
        organic_matter_preference=CropPreferenceLevel.MODERATE,
    )
    db.add_all([field, crop])
    db.commit()

    service = EconomicService(
        db,
        yield_prediction_service=YieldPredictionService(db, model_dir=tmp_path / "yield_model"),
    )
    assessment = service.calculate_profit(
        field,
        crop,
        yield_prediction=_yield_prediction(field.id, crop.id, 4.2),
    )

    assert assessment.estimated_profit is None
    assert assessment.reasons == ["Economic data unavailable for this crop."]
