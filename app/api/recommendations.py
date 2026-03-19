from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.recommendation import RankedFieldResult
from app.engines.suitability_engine import calculate_suitability
from app.engines.explanation_engine import generate_explanation
from app.services.field_service import get_field
from app.services.crop_service import get_crop
from app.services.soil_service import get_latest_soil_test_for_field

router = APIRouter(prefix="/recommendation", tags=["recommendations"])


@router.get("/{field_id}/{crop_id}", response_model=RankedFieldResult)
def get_recommendation(field_id: int, crop_id: int, db: Session = Depends(get_db)):
    field_obj = get_field(db, field_id)
    if not field_obj:
        raise HTTPException(status_code=404, detail="Field not found")
    crop = get_crop(db, crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    soil_test = get_latest_soil_test_for_field(db, field_id)
    result = calculate_suitability(field_obj, crop, soil_test)
    explanation = generate_explanation(result, field_obj, crop)
    return RankedFieldResult(
        rank=1,
        field_id=field_id,
        crop_id=crop_id,
        score=result.total_score,
        explanation=explanation,
    )
