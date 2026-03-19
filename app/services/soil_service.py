from sqlalchemy.orm import Session
from app.models.soil_test import SoilTest
from app.schemas.soil_test import SoilTestCreate
from datetime import datetime, timezone


def create_soil_test(db: Session, soil_data: SoilTestCreate) -> SoilTest:
    data = soil_data.model_dump()
    if data.get("tested_at") is None:
        data["tested_at"] = datetime.now(timezone.utc)
    soil_test = SoilTest(**data)
    db.add(soil_test)
    db.commit()
    db.refresh(soil_test)
    return soil_test


def get_soil_tests(db: Session, skip: int = 0, limit: int = 100) -> list[SoilTest]:
    return db.query(SoilTest).offset(skip).limit(limit).all()


def get_soil_tests_for_field(db: Session, field_id: int) -> list[SoilTest]:
    return db.query(SoilTest).filter(SoilTest.field_id == field_id).all()


def get_latest_soil_test_for_field(db: Session, field_id: int) -> SoilTest | None:
    return (
        db.query(SoilTest)
        .filter(SoilTest.field_id == field_id)
        .order_by(SoilTest.tested_at.desc())
        .first()
    )
