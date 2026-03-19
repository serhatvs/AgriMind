from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.soil_test import SoilTestCreate, SoilTestRead
from app.services import soil_service

router = APIRouter(prefix="/soil-tests", tags=["soil-tests"])


@router.post("/", response_model=SoilTestRead, status_code=201)
def create_soil_test(soil_data: SoilTestCreate, db: Session = Depends(get_db)):
    return soil_service.create_soil_test(db, soil_data)


@router.get("/", response_model=list[SoilTestRead])
def list_soil_tests(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return soil_service.get_soil_tests(db, skip=skip, limit=limit)


@router.get("/field/{field_id}", response_model=list[SoilTestRead])
def get_soil_tests_for_field(field_id: int, db: Session = Depends(get_db)):
    return soil_service.get_soil_tests_for_field(db, field_id)
