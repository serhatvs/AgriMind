"""ORM model for externally sourced crop statistics used by planning features."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Enum, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import ExternalCropStatisticType
from app.models.mixins import CreatedAtMixin


class ExternalCropStatistic(CreatedAtMixin, Base):
    """Annual crop-level statistics imported from external agricultural data sources."""

    __tablename__ = "external_crop_statistics"
    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "country",
            "year",
            "crop_name",
            "statistic_type",
            name="uq_external_crop_statistics_source_country_year_crop_stat",
        ),
        CheckConstraint("year >= 1900", name="ck_external_crop_statistics_year_floor"),
        CheckConstraint("statistic_value >= 0", name="ck_external_crop_statistics_value_non_negative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    crop_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    statistic_type: Mapped[ExternalCropStatisticType] = mapped_column(
        Enum(
            ExternalCropStatisticType,
            name="external_crop_statistic_type_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    statistic_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
