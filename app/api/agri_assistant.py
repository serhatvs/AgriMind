from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.agri_assistant import AgriAssistantAskRequest, AgriAssistantResponse
from app.services.agri_assistant_service import ask_agri_assistant, build_agri_assistant_context
from app.services.ranking_service import get_ranked_fields_response

router = APIRouter(prefix="/agri-assistant", tags=["agri-assistant"])


@router.post("/ask", response_model=AgriAssistantResponse)
def ask_agri_assistant_endpoint(
    request: AgriAssistantAskRequest,
    db: Session = Depends(get_db),
):
    try:
        ranking_response = get_ranked_fields_response(
            db,
            crop_id=request.crop_id,
            top_n=request.top_n,
            field_ids=request.field_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        context = build_agri_assistant_context(
            ranking_response,
            selected_field_id=request.selected_field_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ask_agri_assistant(request.question, context)
