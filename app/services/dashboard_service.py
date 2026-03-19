"""Aggregated dashboard read models for operational data entry flows."""

from __future__ import annotations

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.models.crop_profile import CropProfile
from app.models.field import Field
from app.models.soil_test import SoilTest
from app.schemas.dashboard import (
    DashboardCoverageRead,
    DashboardOverviewRead,
    DashboardRecentCropProfileRead,
    DashboardRecentFieldRead,
    DashboardRecentSoilTestRead,
    DashboardTotalsRead,
)


def get_dashboard_overview(db: Session) -> DashboardOverviewRead:
    """Return one aggregated dashboard payload from live field, soil, and crop data."""

    total_fields = db.query(func.count(Field.id)).scalar() or 0
    total_soil_tests = db.query(func.count(SoilTest.id)).scalar() or 0
    total_crop_profiles = db.query(func.count(CropProfile.id)).scalar() or 0
    fields_with_soil_tests = db.query(func.count(distinct(SoilTest.field_id))).scalar() or 0

    recent_fields = (
        db.query(Field)
        .order_by(Field.updated_at.desc(), Field.id.desc())
        .limit(5)
        .all()
    )
    recent_soil_tests = (
        db.query(SoilTest, Field.name.label("field_name"))
        .join(Field, SoilTest.field_id == Field.id)
        .order_by(SoilTest.sample_date.desc(), SoilTest.created_at.desc(), SoilTest.id.desc())
        .limit(5)
        .all()
    )
    recent_crop_profiles = (
        db.query(CropProfile)
        .order_by(CropProfile.updated_at.desc(), CropProfile.id.desc())
        .limit(5)
        .all()
    )

    return DashboardOverviewRead(
        totals=DashboardTotalsRead(
            fields=total_fields,
            soil_tests=total_soil_tests,
            crop_profiles=total_crop_profiles,
        ),
        coverage=DashboardCoverageRead(
            fields_with_soil_tests=fields_with_soil_tests,
            fields_without_soil_tests=max(0, total_fields - fields_with_soil_tests),
        ),
        recent_fields=[DashboardRecentFieldRead.model_validate(field) for field in recent_fields],
        recent_soil_tests=[
            DashboardRecentSoilTestRead(
                id=soil_test.id,
                field_id=soil_test.field_id,
                field_name=field_name,
                sample_date=soil_test.sample_date,
                created_at=soil_test.created_at,
            )
            for soil_test, field_name in recent_soil_tests
        ],
        recent_crop_profiles=[
            DashboardRecentCropProfileRead.model_validate(crop)
            for crop in recent_crop_profiles
        ],
    )
