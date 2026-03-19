"""Weather history ORM model and weather-specific database constraints."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from app.models.field import Field


class WeatherHistory(CreatedAtMixin, Base):
    """Daily weather observations linked to a field."""

    __tablename__ = "weather_history"
    __table_args__ = (
        UniqueConstraint("field_id", "date", name="uq_weather_history_field_id_date"),
        CheckConstraint(
            "min_temp <= avg_temp AND avg_temp <= max_temp",
            name="ck_weather_history_temperature_order",
        ),
        CheckConstraint("rainfall_mm >= 0", name="ck_weather_history_rainfall_non_negative"),
        CheckConstraint(
            "humidity >= 0 AND humidity <= 100",
            name="ck_weather_history_humidity_range",
        ),
        CheckConstraint("wind_speed >= 0", name="ck_weather_history_wind_speed_non_negative"),
        CheckConstraint(
            "solar_radiation IS NULL OR solar_radiation >= 0",
            name="ck_weather_history_solar_radiation_non_negative",
        ),
        CheckConstraint(
            "et0 IS NULL OR et0 >= 0",
            name="ck_weather_history_et0_non_negative",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    field_id: Mapped[int] = mapped_column(Integer, ForeignKey("fields.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    min_temp: Mapped[float] = mapped_column(Float, nullable=False)
    max_temp: Mapped[float] = mapped_column(Float, nullable=False)
    avg_temp: Mapped[float] = mapped_column(Float, nullable=False)
    rainfall_mm: Mapped[float] = mapped_column(Float, nullable=False)
    humidity: Mapped[float] = mapped_column(Float, nullable=False)
    wind_speed: Mapped[float] = mapped_column(Float, nullable=False)
    solar_radiation: Mapped[float | None] = mapped_column(Float, nullable=True)
    et0: Mapped[float | None] = mapped_column(Float, nullable=True)

    field: Mapped["Field"] = relationship("Field", back_populates="weather_history")
