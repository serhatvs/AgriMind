from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.field import FieldCreate, FieldRead, FieldUpdate
from app.services import field_service

router = APIRouter(prefix="/fields", tags=["fields"])


@router.post("/", response_model=FieldRead, status_code=201)
def create_field(field_data: FieldCreate, db: Session = Depends(get_db)):
    return field_service.create_field(db, field_data)


@router.get("/", response_model=list[FieldRead])
def list_fields(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return field_service.get_fields(db, skip=skip, limit=limit)


@router.get("/{field_id}", response_model=FieldRead)
def get_field(field_id: int, db: Session = Depends(get_db)):
    field = field_service.get_field(db, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return field


@router.put("/{field_id}", response_model=FieldRead)
def update_field(field_id: int, field_data: FieldUpdate, db: Session = Depends(get_db)):
    field = field_service.update_field(db, field_id, field_data)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return field


@router.delete("/{field_id}", status_code=204)
def delete_field(field_id: int, db: Session = Depends(get_db)):
    deleted = field_service.delete_field(db, field_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Field not found")
