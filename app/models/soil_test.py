"""Soil test ORM model and soil-specific database constraints."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import CreatedAtMixin, utc_now

if TYPE_CHECKING:
    from app.models.field import Field


class SoilTest(CreatedAtMixin, Base):
    """Lab soil analysis linked to a field over time."""

    __tablename__ = "soil_tests"
    __table_args__ = (
        CheckConstraint("ph >= 0 AND ph <= 14", name="ck_soil_tests_ph_range"),
        CheckConstraint(
            "ec IS NULL OR ec >= 0",
            name="ck_soil_tests_ec_non_negative",
        ),
        CheckConstraint(
            "organic_matter_percent >= 0 AND organic_matter_percent <= 100",
            name="ck_soil_tests_organic_matter_percent_range",
        ),
        CheckConstraint(
            "nitrogen_ppm >= 0",
            name="ck_soil_tests_nitrogen_ppm_non_negative",
        ),
        CheckConstraint(
            "phosphorus_ppm >= 0",
            name="ck_soil_tests_phosphorus_ppm_non_negative",
        ),
        CheckConstraint(
            "potassium_ppm >= 0",
            name="ck_soil_tests_potassium_ppm_non_negative",
        ),
        CheckConstraint(
            "calcium_ppm IS NULL OR calcium_ppm >= 0",
            name="ck_soil_tests_calcium_ppm_non_negative",
        ),
        CheckConstraint(
            "magnesium_ppm IS NULL OR magnesium_ppm >= 0",
            name="ck_soil_tests_magnesium_ppm_non_negative",
        ),
        CheckConstraint(
            "depth_cm IS NULL OR depth_cm > 0",
            name="ck_soil_tests_depth_cm_positive",
        ),
        CheckConstraint(
            "water_holding_capacity IS NULL OR water_holding_capacity >= 0",
            name="ck_soil_tests_water_holding_capacity_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    field_id: Mapped[int] = mapped_column(Integer, ForeignKey("fields.id"), nullable=False, index=True)
    sample_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ph: Mapped[float] = mapped_column(Float, nullable=False)
    ec: Mapped[float | None] = mapped_column(Float, nullable=True)
    organic_matter_percent: Mapped[float] = mapped_column(Float, nullable=False)
    nitrogen_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    phosphorus_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    potassium_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    calcium_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    magnesium_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    texture_class: Mapped[str] = mapped_column(String(64), nullable=False)
    drainage_class: Mapped[str | None] = mapped_column(String(32), nullable=True)
    depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    water_holding_capacity: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    field: Mapped["Field"] = relationship("Field", back_populates="soil_tests")

    @property
    def ph_level(self) -> float:
        """Temporary compatibility alias for the previous field name."""

        return self.ph

    @property
    def soil_texture(self) -> str:
        """Temporary compatibility alias for the previous field name."""

        return self.texture_class

    @property
    def tested_at(self) -> datetime:
        """Temporary compatibility alias for the previous field name."""

        return self.sample_date
