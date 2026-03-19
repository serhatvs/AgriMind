"""Field ORM model and field-specific database constraints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import FieldAspect, WaterSourceType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.feedback import RecommendationResult, SeasonResult, UserDecision
    from app.models.field_crop_cycle import FieldCropCycle
    from app.models.soil_test import SoilTest
    from app.models.weather_history import WeatherHistory


def _weather_history_order_by():
    from app.models.weather_history import WeatherHistory

    return WeatherHistory.date.desc(), WeatherHistory.created_at.desc()


class Field(TimestampMixin, Base):
    """Core field record used across agronomic evaluation workflows."""

    __tablename__ = "fields"
    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
            name="ck_fields_latitude_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
            name="ck_fields_longitude_range",
        ),
        CheckConstraint("area_hectares > 0", name="ck_fields_area_hectares_positive"),
        CheckConstraint(
            "slope_percent >= 0 AND slope_percent <= 100",
            name="ck_fields_slope_percent_range",
        ),
        CheckConstraint(
            "infrastructure_score >= 0 AND infrastructure_score <= 100",
            name="ck_fields_infrastructure_score_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    area_hectares: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    slope_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    aspect: Mapped[FieldAspect | None] = mapped_column(
        Enum(FieldAspect, name="field_aspect_enum"),
        nullable=True,
    )
    irrigation_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    water_source_type: Mapped[WaterSourceType | None] = mapped_column(
        Enum(WaterSourceType, name="water_source_type_enum"),
        nullable=True,
    )
    infrastructure_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    drainage_quality: Mapped[str] = mapped_column(String(32), default="moderate", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    soil_tests: Mapped[list["SoilTest"]] = relationship(
        "SoilTest",
        back_populates="field",
        cascade="all, delete-orphan",
    )
    weather_history: Mapped[list["WeatherHistory"]] = relationship(
        "WeatherHistory",
        back_populates="field",
        cascade="all, delete-orphan",
        order_by=_weather_history_order_by,
    )
    recommendation_results: Mapped[list["RecommendationResult"]] = relationship(
        "RecommendationResult",
        back_populates="field",
    )
    user_decisions: Mapped[list["UserDecision"]] = relationship(
        "UserDecision",
        back_populates="selected_field",
    )
    season_results: Mapped[list["SeasonResult"]] = relationship(
        "SeasonResult",
        back_populates="field",
    )
    crop_cycle: Mapped["FieldCropCycle | None"] = relationship(
        "FieldCropCycle",
        back_populates="field",
        cascade="all, delete-orphan",
        uselist=False,
    )
