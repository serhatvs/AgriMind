from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.ranking import RankFieldsRequest, RankFieldsResponse
from app.services.ranking_service import get_ranked_fields_response

router = APIRouter(prefix="/rank-fields", tags=["ranking"])


@router.post("/", response_model=RankFieldsResponse)
def rank_fields_endpoint(request: RankFieldsRequest, db: Session = Depends(get_db)):
    try:
        return get_ranked_fields_response(
            db,
            crop_id=request.crop_id,
            top_n=request.top_n,
            field_ids=request.field_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
