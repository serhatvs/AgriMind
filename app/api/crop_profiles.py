from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.service_errors import raise_http_exception_for_service_error
from app.database import get_db
from app.schemas.crop_profile import CropProfileCreate, CropProfileRead, CropProfileUpdate
from app.services import crop_catalog_service

router = APIRouter(prefix="/crop-profiles", tags=["crop-profiles"])


@router.post("/", response_model=CropProfileRead, status_code=201)
def create_crop_profile(crop_data: CropProfileCreate, db: Session = Depends(get_db)):
    try:
        return crop_catalog_service.create_crop(db, crop_data)
    except Exception as exc:
        raise_http_exception_for_service_error(exc)


@router.get("/", response_model=list[CropProfileRead])
def list_crop_profiles(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return crop_catalog_service.list_crops(db, skip=skip, limit=limit)


@router.get("/{crop_id}", response_model=CropProfileRead)
def get_crop_profile(crop_id: str, db: Session = Depends(get_db)):
    try:
        return crop_catalog_service.get_crop(db, crop_id)
    except Exception as exc:
        raise_http_exception_for_service_error(exc)


@router.put("/{crop_id}", response_model=CropProfileRead)
def update_crop_profile(crop_id: str, crop_data: CropProfileUpdate, db: Session = Depends(get_db)):
    try:
        return crop_catalog_service.update_crop(db, crop_id, crop_data)
    except Exception as exc:
        raise_http_exception_for_service_error(exc)
