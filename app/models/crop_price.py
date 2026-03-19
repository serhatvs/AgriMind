"""Crop price ORM model for crop-scoped market price inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.crop_profile import CropProfile


class CropPrice(Base):
    """Market price per ton for a crop used in profitability scoring."""

    __tablename__ = "crop_prices"
    __table_args__ = (
        UniqueConstraint("crop_id", name="uq_crop_prices_crop_id"),
        CheckConstraint("price_per_ton > 0", name="ck_crop_prices_price_per_ton_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    crop_id: Mapped[int] = mapped_column(Integer, ForeignKey("crop_profiles.id"), nullable=False, index=True)
    price_per_ton: Mapped[float] = mapped_column(Float, nullable=False)

    crop: Mapped["CropProfile"] = relationship("CropProfile", back_populates="crop_price")
