from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.service_errors import raise_http_exception_for_service_error
from app.database import get_db
from app.schemas.crop_profile import CropProfileCreate, CropProfileRead, CropProfileUpdate
from app.services import crop_service
from app.services.errors import NotFoundError

router = APIRouter(prefix="/crops", tags=["crops"])


@router.post("/", response_model=CropProfileRead, status_code=201)
def create_crop(crop_data: CropProfileCreate, db: Session = Depends(get_db)):
    try:
        return crop_service.create_crop(db, crop_data)
    except Exception as exc:
        raise_http_exception_for_service_error(exc)


@router.get("/", response_model=list[CropProfileRead])
def list_crops(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crop_service.get_crops(db, skip=skip, limit=limit)


@router.get("/{crop_id}", response_model=CropProfileRead)
def get_crop(crop_id: int, db: Session = Depends(get_db)):
    crop = crop_service.get_crop(db, crop_id)
    if not crop:
        raise_http_exception_for_service_error(NotFoundError("Crop not found"))
    return crop


@router.put("/{crop_id}", response_model=CropProfileRead)
def update_crop(crop_id: int, crop_data: CropProfileUpdate, db: Session = Depends(get_db)):
    try:
        return crop_service.update_crop(db, crop_id, crop_data)
    except Exception as exc:
        raise_http_exception_for_service_error(exc)
