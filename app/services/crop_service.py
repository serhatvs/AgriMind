from sqlalchemy.orm import Session
from app.models.crop_profile import CropProfile
from app.schemas.crop_profile import CropProfileCreate


def create_crop(db: Session, crop_data: CropProfileCreate) -> CropProfile:
    crop = CropProfile(**crop_data.model_dump())
    db.add(crop)
    db.commit()
    db.refresh(crop)
    return crop


def get_crop(db: Session, crop_id: int) -> CropProfile | None:
    return db.query(CropProfile).filter(CropProfile.id == crop_id).first()


def get_crops(db: Session, skip: int = 0, limit: int = 100) -> list[CropProfile]:
    return db.query(CropProfile).offset(skip).limit(limit).all()


def get_crop_by_name(db: Session, name: str) -> CropProfile | None:
    return db.query(CropProfile).filter(CropProfile.crop_name == name).first()
