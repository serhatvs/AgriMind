from sqlalchemy.orm import Session
from app.models.field import Field
from app.schemas.field import FieldCreate, FieldUpdate
from datetime import datetime, timezone


def create_field(db: Session, field_data: FieldCreate) -> Field:
    field = Field(**field_data.model_dump())
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


def get_field(db: Session, field_id: int) -> Field | None:
    return db.query(Field).filter(Field.id == field_id).first()


def get_fields(db: Session, skip: int = 0, limit: int = 100) -> list[Field]:
    return db.query(Field).offset(skip).limit(limit).all()


def update_field(db: Session, field_id: int, field_data: FieldUpdate) -> Field | None:
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        return None
    update_data = field_data.model_dump(exclude_unset=True)
    update_data["updated_at"] = datetime.now(timezone.utc)
    for key, value in update_data.items():
        setattr(field, key, value)
    db.commit()
    db.refresh(field)
    return field


def delete_field(db: Session, field_id: int) -> bool:
    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        return False
    db.delete(field)
    db.commit()
    return True
