from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.crop_profile import CropProfile
from app.schemas.crop_profile import CropProfileCreate, CropProfileUpdate
from app.services.errors import ConflictError, NotFoundError


def _commit(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def create_crop(db: Session, crop_data: CropProfileCreate) -> CropProfile:
    _ensure_unique_crop_name(db, crop_data.crop_name)
    crop = CropProfile(**crop_data.model_dump(mode="json"))
    db.add(crop)
    _commit(db)
    db.refresh(crop)
    return crop


def get_crop(db: Session, crop_id: int) -> CropProfile | None:
    return db.query(CropProfile).filter(CropProfile.id == crop_id).first()


def get_crops(db: Session, skip: int = 0, limit: int = 100) -> list[CropProfile]:
    return db.query(CropProfile).offset(skip).limit(limit).all()


def get_crop_by_name(db: Session, name: str) -> CropProfile | None:
    return db.query(CropProfile).filter(CropProfile.crop_name == name).first()


def update_crop(db: Session, crop_id: int, crop_data: CropProfileUpdate) -> CropProfile:
    crop = get_crop(db, crop_id)
    if crop is None:
        raise NotFoundError("Crop not found")

    update_data = crop_data.model_dump(mode="json", exclude_unset=True)
    if "crop_name" in update_data:
        _ensure_unique_crop_name(db, update_data["crop_name"], exclude_crop_id=crop_id)

    for key, value in update_data.items():
        setattr(crop, key, value)

    _commit(db)
    db.refresh(crop)
    return crop


def _ensure_unique_crop_name(db: Session, crop_name: str, exclude_crop_id: int | None = None) -> None:
    existing_query = db.query(CropProfile).filter(func.lower(CropProfile.crop_name) == crop_name.lower())
    if exclude_crop_id is not None:
        existing_query = existing_query.filter(CropProfile.id != exclude_crop_id)

    existing_crop = existing_query.first()
    if existing_crop is not None:
        raise ConflictError(f"Crop profile with name '{crop_name}' already exists")
