from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.service_errors import raise_http_exception_for_service_error
from app.database import get_db
from app.schemas.soil_test import SoilTestCreate, SoilTestRead, SoilTestUpdate
from app.services import soil_service

router = APIRouter(prefix="/soil-tests", tags=["soil-tests"])


@router.post("/", response_model=SoilTestRead, status_code=201)
def create_soil_test(soil_data: SoilTestCreate, db: Session = Depends(get_db)):
    try:
        return soil_service.create_soil_test(db, soil_data)
    except Exception as exc:
        raise_http_exception_for_service_error(exc)


@router.get("/", response_model=list[SoilTestRead])
def list_soil_tests(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return soil_service.get_soil_tests(db, skip=skip, limit=limit)


@router.get("/field/{field_id}", response_model=list[SoilTestRead])
def get_soil_tests_for_field(field_id: int, db: Session = Depends(get_db)):
    return soil_service.get_soil_tests_for_field(db, field_id)


@router.put("/{soil_test_id}", response_model=SoilTestRead)
def update_soil_test(soil_test_id: int, soil_data: SoilTestUpdate, db: Session = Depends(get_db)):
    try:
        return soil_service.update_soil_test(db, soil_test_id, soil_data)
    except Exception as exc:
        raise_http_exception_for_service_error(exc)
