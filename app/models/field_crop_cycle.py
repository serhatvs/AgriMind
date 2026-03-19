"""Field crop cycle ORM model for active crop lifecycle tracking."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile
    from app.models.field import Field


class FieldCropCycle(TimestampMixin, Base):
    """Active crop cycle assigned to a field."""

    __tablename__ = "field_crop_cycles"
    __table_args__ = (UniqueConstraint("field_id", name="uq_field_crop_cycles_field_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    field_id: Mapped[int] = mapped_column(Integer, ForeignKey("fields.id"), nullable=False)
    crop_id: Mapped[int] = mapped_column(Integer, ForeignKey("crop_profiles.id"), nullable=False, index=True)
    sowing_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_stage: Mapped[str] = mapped_column(String(255), nullable=False)

    field: Mapped["Field"] = relationship("Field", back_populates="crop_cycle")
    crop: Mapped["CropProfile"] = relationship("CropProfile", back_populates="field_crop_cycles")
