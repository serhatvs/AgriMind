"""Crop profile ORM model for agronomic crop requirement records."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, CheckConstraint, Enum, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.crop_price import CropPrice
    from app.models.field_crop_cycle import FieldCropCycle
    from app.models.feedback import RecommendationRun, SeasonResult
    from app.models.input_cost import InputCost


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
        CheckConstraint(
            "optimal_temp_min_c IS NULL OR optimal_temp_max_c IS NULL OR optimal_temp_min_c <= optimal_temp_max_c",
            name="ck_crop_profiles_optimal_temp_order",
        ),
        CheckConstraint(
            "tolerable_temp_min_c IS NULL OR tolerable_temp_max_c IS NULL OR tolerable_temp_min_c <= tolerable_temp_max_c",
            name="ck_crop_profiles_tolerable_temp_order",
        ),
        CheckConstraint(
            "optimal_temp_min_c IS NULL OR tolerable_temp_min_c IS NULL OR tolerable_temp_min_c <= optimal_temp_min_c",
            name="ck_crop_profiles_tolerable_temp_min_not_above_optimal_min",
        ),
        CheckConstraint(
            "optimal_temp_max_c IS NULL OR tolerable_temp_max_c IS NULL OR optimal_temp_max_c <= tolerable_temp_max_c",
            name="ck_crop_profiles_optimal_temp_max_not_above_tolerable_max",
        ),
        CheckConstraint(
            "rainfall_requirement_mm IS NULL OR rainfall_requirement_mm >= 0",
            name="ck_crop_profiles_rainfall_requirement_non_negative",
        ),
        CheckConstraint(
            "preferred_rainfall_min_mm IS NULL OR preferred_rainfall_min_mm >= 0",
            name="ck_crop_profiles_preferred_rainfall_min_non_negative",
        ),
        CheckConstraint(
            "preferred_rainfall_max_mm IS NULL OR preferred_rainfall_max_mm >= 0",
            name="ck_crop_profiles_preferred_rainfall_max_non_negative",
        ),
        CheckConstraint(
            "preferred_rainfall_min_mm IS NULL OR preferred_rainfall_max_mm IS NULL OR preferred_rainfall_min_mm <= preferred_rainfall_max_mm",
            name="ck_crop_profiles_preferred_rainfall_order",
        ),
        CheckConstraint(
            "frost_tolerance_days IS NULL OR frost_tolerance_days >= 0",
            name="ck_crop_profiles_frost_tolerance_non_negative",
        ),
        CheckConstraint(
            "heat_tolerance_days IS NULL OR heat_tolerance_days >= 0",
            name="ck_crop_profiles_heat_tolerance_non_negative",
        ),
        CheckConstraint(
            "target_nitrogen_ppm IS NULL OR target_nitrogen_ppm >= 0",
            name="ck_crop_profiles_target_nitrogen_ppm_non_negative",
        ),
        CheckConstraint(
            "target_phosphorus_ppm IS NULL OR target_phosphorus_ppm >= 0",
            name="ck_crop_profiles_target_phosphorus_ppm_non_negative",
        ),
        CheckConstraint(
            "target_potassium_ppm IS NULL OR target_potassium_ppm >= 0",
            name="ck_crop_profiles_target_potassium_ppm_non_negative",
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
    optimal_temp_min_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    optimal_temp_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    tolerable_temp_min_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    tolerable_temp_max_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_requirement_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_rainfall_min_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    preferred_rainfall_max_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    frost_tolerance_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heat_tolerance_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_nitrogen_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_phosphorus_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_potassium_ppm: Mapped[float | None] = mapped_column(Float, nullable=True)
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
    growth_stages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    crop_price: Mapped["CropPrice | None"] = relationship(
        "CropPrice",
        back_populates="crop",
        cascade="all, delete-orphan",
        uselist=False,
    )
    input_cost: Mapped["InputCost | None"] = relationship(
        "InputCost",
        back_populates="crop",
        cascade="all, delete-orphan",
        uselist=False,
    )
    recommendation_runs: Mapped[list["RecommendationRun"]] = relationship(
        "RecommendationRun",
        back_populates="crop",
    )
    season_results: Mapped[list["SeasonResult"]] = relationship(
        "SeasonResult",
        back_populates="crop",
    )
    field_crop_cycles: Mapped[list["FieldCropCycle"]] = relationship(
        "FieldCropCycle",
        back_populates="crop",
    )

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
        """Compatibility alias for persisted crop nitrogen sufficiency targets."""

        return self.target_nitrogen_ppm if self.target_nitrogen_ppm is not None else 0.0

    @property
    def min_phosphorus_ppm(self) -> float:
        """Compatibility alias for persisted crop phosphorus sufficiency targets."""

        return self.target_phosphorus_ppm if self.target_phosphorus_ppm is not None else 0.0

    @property
    def min_potassium_ppm(self) -> float:
        """Compatibility alias for persisted crop potassium sufficiency targets."""

        return self.target_potassium_ppm if self.target_potassium_ppm is not None else 0.0

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

    @property
    def optimal_temp_range(self) -> tuple[float | None, float | None]:
        """Compatibility view of the crop's optimal average temperature band."""

        return (self.optimal_temp_min_c, self.optimal_temp_max_c)

    @property
    def rainfall_requirement(self) -> float | None:
        """Compatibility alias for the crop rainfall target."""

        return self.rainfall_requirement_mm

    @property
    def optimal_temp_min(self) -> float | None:
        """Compatibility alias for the crop's preferred minimum average temperature."""

        return self.optimal_temp_min_c

    @property
    def optimal_temp_max(self) -> float | None:
        """Compatibility alias for the crop's preferred maximum average temperature."""

        return self.optimal_temp_max_c

    @property
    def tolerable_temp_min(self) -> float | None:
        """Compatibility alias for the crop's tolerable minimum average temperature."""

        return self.tolerable_temp_min_c

    @property
    def tolerable_temp_max(self) -> float | None:
        """Compatibility alias for the crop's tolerable maximum average temperature."""

        return self.tolerable_temp_max_c

    @property
    def preferred_rainfall_min(self) -> float | None:
        """Compatibility alias for the crop's preferred minimum lookback rainfall."""

        return self.preferred_rainfall_min_mm

    @property
    def preferred_rainfall_max(self) -> float | None:
        """Compatibility alias for the crop's preferred maximum lookback rainfall."""

        return self.preferred_rainfall_max_mm

    @property
    def frost_tolerance(self) -> int | None:
        """Compatibility alias for the crop frost-day tolerance."""

        return self.frost_tolerance_days

    @property
    def heat_tolerance(self) -> int | None:
        """Compatibility alias for the crop heat-day tolerance."""

        return self.heat_tolerance_days
