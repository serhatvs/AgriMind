from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.crop_profile import CropProfileCreate, CropProfileRead
from app.services import crop_service

router = APIRouter(prefix="/crops", tags=["crops"])


@router.post("/", response_model=CropProfileRead, status_code=201)
def create_crop(crop_data: CropProfileCreate, db: Session = Depends(get_db)):
    return crop_service.create_crop(db, crop_data)


@router.get("/", response_model=list[CropProfileRead])
def list_crops(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crop_service.get_crops(db, skip=skip, limit=limit)


@router.get("/{crop_id}", response_model=CropProfileRead)
def get_crop(crop_id: int, db: Session = Depends(get_db)):
    crop = crop_service.get_crop(db, crop_id)
    if not crop:
        raise HTTPException(status_code=404, detail="Crop not found")
    return crop
