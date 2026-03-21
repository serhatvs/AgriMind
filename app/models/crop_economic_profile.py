"""Crop-scoped economic profile ORM model used for profitability scoring."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import TimestampMixin


class CropEconomicProfile(TimestampMixin, Base):
    """Reusable economic assumptions for crop-level profitability estimation."""

    __tablename__ = "crop_economic_profiles"
    __table_args__ = (
        UniqueConstraint("crop_name", "region", name="uq_crop_economic_profiles_crop_region"),
        CheckConstraint(
            "average_market_price_per_unit > 0",
            name="ck_crop_economic_profiles_average_market_price_positive",
        ),
        CheckConstraint(
            "base_cost_per_hectare >= 0",
            name="ck_crop_economic_profiles_base_cost_non_negative",
        ),
        CheckConstraint(
            "irrigation_cost_factor >= 0",
            name="ck_crop_economic_profiles_irrigation_cost_factor_non_negative",
        ),
        CheckConstraint(
            "fertilizer_cost_factor >= 0",
            name="ck_crop_economic_profiles_fertilizer_cost_factor_non_negative",
        ),
        CheckConstraint(
            "labor_cost_factor >= 0",
            name="ck_crop_economic_profiles_labor_cost_factor_non_negative",
        ),
        CheckConstraint(
            "risk_cost_factor >= 0",
            name="ck_crop_economic_profiles_risk_cost_factor_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    crop_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    average_market_price_per_unit: Mapped[float] = mapped_column(Float, nullable=False)
    price_unit: Mapped[str] = mapped_column(String(64), nullable=False, default="ton")
    base_cost_per_hectare: Mapped[float] = mapped_column(Float, nullable=False)
    irrigation_cost_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fertilizer_cost_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    labor_cost_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_cost_factor: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    region: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
