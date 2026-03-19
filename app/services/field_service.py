"""Persistence operations for the field domain."""

from sqlalchemy.orm import Session

from app.models.field import Field
from app.schemas.field import FieldCreate, FieldUpdate


def create_field(db: Session, field_data: FieldCreate) -> Field:
    """Create and persist a new field record."""

    field = Field(**field_data.model_dump())
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


def get_field(db: Session, field_id: int) -> Field | None:
    """Fetch a field by primary key."""

    return db.query(Field).filter(Field.id == field_id).first()


def get_fields(db: Session, skip: int = 0, limit: int = 100) -> list[Field]:
    """Fetch a paginated list of fields."""

    return db.query(Field).offset(skip).limit(limit).all()


def get_all_fields(db: Session) -> list[Field]:
    """Fetch all fields in a deterministic order for ranking workflows."""

    return db.query(Field).order_by(Field.id.asc()).all()


def get_fields_by_ids(db: Session, field_ids: list[int]) -> list[Field]:
    """Fetch a subset of fields while preserving the requested ID order."""

    unique_ids = list(dict.fromkeys(field_ids))
    if not unique_ids:
        return []

    fields = db.query(Field).filter(Field.id.in_(unique_ids)).all()
    fields_by_id = {field.id: field for field in fields}
    return [fields_by_id[field_id] for field_id in unique_ids if field_id in fields_by_id]


def update_field(db: Session, field_id: int, field_data: FieldUpdate) -> Field | None:
    """Update an existing field with a partial payload."""

    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        return None

    update_data = field_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(field, key, value)

    db.commit()
    db.refresh(field)
    return field


def delete_field(db: Session, field_id: int) -> bool:
    """Delete a field if it exists."""

    field = db.query(Field).filter(Field.id == field_id).first()
    if not field:
        return False
    db.delete(field)
    db.commit()
    return True
