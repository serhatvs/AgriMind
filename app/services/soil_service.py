"""Persistence operations for the soil test domain."""

from sqlalchemy.orm import Session

from app.models.mixins import utc_now
from app.models.soil_test import SoilTest
from app.schemas.soil_test import SoilTestCreate


def create_soil_test(db: Session, soil_data: SoilTestCreate) -> SoilTest:
    """Create and persist a soil test."""

    data = soil_data.model_dump()
    if data.get("sample_date") is None:
        data["sample_date"] = utc_now()
    soil_test = SoilTest(**data)
    db.add(soil_test)
    db.commit()
    db.refresh(soil_test)
    return soil_test


def get_soil_tests(db: Session, skip: int = 0, limit: int = 100) -> list[SoilTest]:
    """Fetch a paginated list of soil tests."""

    return db.query(SoilTest).offset(skip).limit(limit).all()


def get_soil_tests_for_field(db: Session, field_id: int) -> list[SoilTest]:
    """Fetch all soil tests associated with a field."""

    return db.query(SoilTest).filter(SoilTest.field_id == field_id).all()


def get_latest_soil_test_for_field(db: Session, field_id: int) -> SoilTest | None:
    """Fetch the newest soil test for a field."""

    return (
        db.query(SoilTest)
        .filter(SoilTest.field_id == field_id)
        .order_by(SoilTest.sample_date.desc(), SoilTest.created_at.desc())
        .first()
    )
