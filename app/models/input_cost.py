"""Input cost ORM model for crop-scoped production cost inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile


class InputCost(Base):
    """Per-hectare production cost inputs for a crop."""

    __tablename__ = "input_costs"
    __table_args__ = (
        UniqueConstraint("crop_id", name="uq_input_costs_crop_id"),
        CheckConstraint("fertilizer_cost >= 0", name="ck_input_costs_fertilizer_cost_non_negative"),
        CheckConstraint("water_cost >= 0", name="ck_input_costs_water_cost_non_negative"),
        CheckConstraint("labor_cost >= 0", name="ck_input_costs_labor_cost_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    crop_id: Mapped[int] = mapped_column(Integer, ForeignKey("crop_profiles.id"), nullable=False, index=True)
    fertilizer_cost: Mapped[float] = mapped_column(Float, nullable=False)
    water_cost: Mapped[float] = mapped_column(Float, nullable=False)
    labor_cost: Mapped[float] = mapped_column(Float, nullable=False)

    crop: Mapped["CropProfile"] = relationship("CropProfile", back_populates="input_cost")
