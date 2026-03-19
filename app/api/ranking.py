from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.recommendation import RankFieldsRequest, RankedFieldResult
from app.engines.ranking_engine import rank_fields
from app.engines.explanation_engine import generate_explanation
from app.services.field_service import get_field
from app.services.crop_service import get_crop

router = APIRouter(prefix="/rank-fields", tags=["ranking"])


@router.post("/", response_model=list[RankedFieldResult])
def rank_fields_endpoint(request: RankFieldsRequest, db: Session = Depends(get_db)):
    try:
        ranking = rank_fields(db, request.field_ids, request.crop_id, request.top_n)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    crop = get_crop(db, request.crop_id)
    results = []
    for entry in ranking.ranked_fields:
        field_obj = get_field(db, entry.field_id)
        explanation = generate_explanation(entry.result, field_obj, crop)
        results.append(
            RankedFieldResult(
                rank=entry.rank,
                field_id=entry.field_id,
                crop_id=entry.crop_id,
                score=entry.score,
                explanation=explanation,
            )
        )
    return results
