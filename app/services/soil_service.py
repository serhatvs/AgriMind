"""Persistence operations for the soil test domain."""

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.mixins import utc_now
from app.models.soil_test import SoilTest
from app.schemas.soil_test import SoilTestCreate, SoilTestUpdate
from app.services.errors import NotFoundError
from app.services.field_service import get_field


def _commit(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise


def create_soil_test(db: Session, soil_data: SoilTestCreate) -> SoilTest:
    """Create and persist a soil test."""

    data = soil_data.model_dump()
    _ensure_field_exists(db, data["field_id"])
    if data.get("sample_date") is None:
        data["sample_date"] = utc_now()
    soil_test = SoilTest(**data)
    db.add(soil_test)
    _commit(db)
    db.refresh(soil_test)
    return soil_test


def get_soil_test(db: Session, soil_test_id: int) -> SoilTest | None:
    """Fetch a soil test by primary key."""

    return db.query(SoilTest).filter(SoilTest.id == soil_test_id).first()


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


def update_soil_test(db: Session, soil_test_id: int, soil_data: SoilTestUpdate) -> SoilTest:
    """Update an existing soil test with a partial payload."""

    soil_test = get_soil_test(db, soil_test_id)
    if soil_test is None:
        raise NotFoundError("Soil test not found")

    update_data = soil_data.model_dump(exclude_unset=True)
    if "field_id" in update_data:
        _ensure_field_exists(db, update_data["field_id"])

    for key, value in update_data.items():
        setattr(soil_test, key, value)

    _commit(db)
    db.refresh(soil_test)
    return soil_test


def _ensure_field_exists(db: Session, field_id: int) -> None:
    if get_field(db, field_id) is None:
        raise NotFoundError(f"Field with id {field_id} not found")
