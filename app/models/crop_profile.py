"""Crop profile ORM model for agronomic crop requirement records."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
)
from app.models.mixins import TimestampMixin


class CropProfile(TimestampMixin, Base):
    """Agronomic crop requirement profile used for field suitability scoring."""

    __tablename__ = "crop_profiles"
    __table_args__ = (
        CheckConstraint(
            "ideal_ph_min >= 0 AND ideal_ph_min <= 14",
            name="ck_crop_profiles_ideal_ph_min_range",
        ),
        CheckConstraint(
            "ideal_ph_max >= 0 AND ideal_ph_max <= 14",
            name="ck_crop_profiles_ideal_ph_max_range",
        ),
        CheckConstraint(
            "tolerable_ph_min >= 0 AND tolerable_ph_min <= 14",
            name="ck_crop_profiles_tolerable_ph_min_range",
        ),
        CheckConstraint(
            "tolerable_ph_max >= 0 AND tolerable_ph_max <= 14",
            name="ck_crop_profiles_tolerable_ph_max_range",
        ),
        CheckConstraint(
            "ideal_ph_min <= ideal_ph_max",
            name="ck_crop_profiles_ideal_ph_order",
        ),
        CheckConstraint(
            "tolerable_ph_min <= tolerable_ph_max",
            name="ck_crop_profiles_tolerable_ph_order",
        ),
        CheckConstraint(
            "tolerable_ph_min <= ideal_ph_min",
            name="ck_crop_profiles_tolerable_min_not_above_ideal_min",
        ),
        CheckConstraint(
            "ideal_ph_max <= tolerable_ph_max",
            name="ck_crop_profiles_ideal_max_not_above_tolerable_max",
        ),
        CheckConstraint(
            "rooting_depth_cm IS NULL OR rooting_depth_cm > 0",
            name="ck_crop_profiles_rooting_depth_cm_positive",
        ),
        CheckConstraint(
            "slope_tolerance IS NULL OR (slope_tolerance >= 0 AND slope_tolerance <= 100)",
            name="ck_crop_profiles_slope_tolerance_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    crop_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scientific_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ideal_ph_min: Mapped[float] = mapped_column(Float, nullable=False)
    ideal_ph_max: Mapped[float] = mapped_column(Float, nullable=False)
    tolerable_ph_min: Mapped[float] = mapped_column(Float, nullable=False)
    tolerable_ph_max: Mapped[float] = mapped_column(Float, nullable=False)
    water_requirement_level: Mapped[WaterRequirementLevel] = mapped_column(
        Enum(
            WaterRequirementLevel,
            name="crop_water_requirement_level_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    drainage_requirement: Mapped[CropDrainageRequirement] = mapped_column(
        Enum(
            CropDrainageRequirement,
            name="crop_drainage_requirement_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    frost_sensitivity: Mapped[CropSensitivityLevel] = mapped_column(
        Enum(
            CropSensitivityLevel,
            name="crop_frost_sensitivity_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    heat_sensitivity: Mapped[CropSensitivityLevel] = mapped_column(
        Enum(
            CropSensitivityLevel,
            name="crop_heat_sensitivity_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=False,
    )
    salinity_tolerance: Mapped[CropPreferenceLevel | None] = mapped_column(
        Enum(
            CropPreferenceLevel,
            name="crop_salinity_tolerance_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    rooting_depth_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    slope_tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)
    organic_matter_preference: Mapped[CropPreferenceLevel | None] = mapped_column(
        Enum(
            CropPreferenceLevel,
            name="crop_organic_matter_preference_enum",
            native_enum=False,
            validate_strings=True,
        ),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def name(self) -> str:
        """Compatibility alias for the legacy crop name attribute."""

        return self.crop_name

    @property
    def optimal_ph_min(self) -> float:
        """Compatibility alias for the prior ideal pH minimum field name."""

        return self.ideal_ph_min

    @property
    def optimal_ph_max(self) -> float:
        """Compatibility alias for the prior ideal pH maximum field name."""

        return self.ideal_ph_max

    @property
    def min_ph(self) -> float:
        """Compatibility alias for the prior tolerable pH minimum field name."""

        return self.tolerable_ph_min

    @property
    def max_ph(self) -> float:
        """Compatibility alias for the prior tolerable pH maximum field name."""

        return self.tolerable_ph_max

    @property
    def water_requirement(self) -> str:
        """Compatibility alias for the prior irrigation requirement field name."""

        return self.water_requirement_level.value

    @property
    def min_nitrogen_ppm(self) -> float:
        """Fallback used by the legacy scoring engine when nutrient minima are absent."""

        return 0.0

    @property
    def min_phosphorus_ppm(self) -> float:
        """Fallback used by the legacy scoring engine when nutrient minima are absent."""

        return 0.0

    @property
    def min_potassium_ppm(self) -> float:
        """Fallback used by the legacy scoring engine when nutrient minima are absent."""

        return 0.0

    @property
    def preferred_soil_textures(self) -> str:
        """Fallback used when no crop-level texture preference is stored."""

        return ""

    @property
    def min_area_hectares(self) -> float:
        """Compatibility alias retained for older ranking logic."""

        return 0.0

    @property
    def max_slope_percent(self) -> float:
        """Compatibility alias for the prior slope tolerance field name."""

        return self.slope_tolerance if self.slope_tolerance is not None else 100.0
