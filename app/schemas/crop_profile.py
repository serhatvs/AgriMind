"""Pydantic schemas for crop agronomic requirement profiles."""

from datetime import datetime
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    CropDrainageRequirement,
    ManagementNeedLevel,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
)


class GrowthStageDefinition(BaseModel):
    """Ordered lifecycle stage definition embedded in a crop profile."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=255)
    duration_days: int = Field(..., gt=0)
    irrigation_need: ManagementNeedLevel
    fertilizer_need: ManagementNeedLevel

    @field_validator("name")
    @classmethod
    def validate_stage_name(cls, value: str) -> str:
        """Reject blank stage names after whitespace normalization."""

        if not value:
            raise ValueError("Stage name must not be empty.")
        return value


class CropProfileBase(BaseModel):
    """Shared crop profile attributes and validation rules."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    crop_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("crop_name", "name"),
    )
    scientific_name: str | None = Field(default=None, min_length=1, max_length=255)
    ideal_ph_min: float | None = Field(
        default=None,
        ge=0,
        le=14,
        validation_alias=AliasChoices("ideal_ph_min", "optimal_ph_min"),
    )
    ideal_ph_max: float | None = Field(
        default=None,
        ge=0,
        le=14,
        validation_alias=AliasChoices("ideal_ph_max", "optimal_ph_max"),
    )
    tolerable_ph_min: float | None = Field(
        default=None,
        ge=0,
        le=14,
        validation_alias=AliasChoices("tolerable_ph_min", "min_ph"),
    )
    tolerable_ph_max: float | None = Field(
        default=None,
        ge=0,
        le=14,
        validation_alias=AliasChoices("tolerable_ph_max", "max_ph"),
    )
    water_requirement_level: WaterRequirementLevel | None = Field(
        default=None,
        validation_alias=AliasChoices("water_requirement_level", "water_requirement"),
    )
    drainage_requirement: CropDrainageRequirement | None = None
    frost_sensitivity: CropSensitivityLevel | None = None
    heat_sensitivity: CropSensitivityLevel | None = None
    salinity_tolerance: CropPreferenceLevel | None = None
    rooting_depth_cm: float | None = Field(default=None, gt=0)
    slope_tolerance: float | None = Field(
        default=None,
        ge=0,
        le=100,
        validation_alias=AliasChoices("slope_tolerance", "max_slope_percent"),
    )
    optimal_temp_min_c: float | None = None
    optimal_temp_max_c: float | None = None
    tolerable_temp_min_c: float | None = Field(
        default=None,
        validation_alias=AliasChoices("tolerable_temp_min_c", "tolerable_temp_min"),
    )
    tolerable_temp_max_c: float | None = Field(
        default=None,
        validation_alias=AliasChoices("tolerable_temp_max_c", "tolerable_temp_max"),
    )
    rainfall_requirement_mm: float | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("rainfall_requirement_mm", "rainfall_requirement"),
    )
    preferred_rainfall_min_mm: float | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("preferred_rainfall_min_mm", "preferred_rainfall_min"),
    )
    preferred_rainfall_max_mm: float | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("preferred_rainfall_max_mm", "preferred_rainfall_max"),
    )
    frost_tolerance_days: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("frost_tolerance_days", "frost_tolerance"),
    )
    heat_tolerance_days: int | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("heat_tolerance_days", "heat_tolerance"),
    )
    target_nitrogen_ppm: float | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("target_nitrogen_ppm", "min_nitrogen_ppm"),
    )
    target_phosphorus_ppm: float | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("target_phosphorus_ppm", "min_phosphorus_ppm"),
    )
    target_potassium_ppm: float | None = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("target_potassium_ppm", "min_potassium_ppm"),
    )
    organic_matter_preference: CropPreferenceLevel | None = None
    notes: str | None = None
    growth_stages: list[GrowthStageDefinition] = Field(default_factory=list)

    @field_validator("crop_name", "scientific_name")
    @classmethod
    def validate_non_empty_strings(cls, value: str | None) -> str | None:
        """Reject blank values for core crop identity fields."""

        if value is None:
            return value
        if not value:
            raise ValueError("Value must not be empty.")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        """Normalize blank notes to null for cleaner persistence."""

        if value == "":
            return None
        return value

    @model_validator(mode="after")
    def validate_ph_ranges(self) -> "CropProfileBase":
        """Ensure ideal pH ranges sit inside tolerable bounds when present."""

        if self.ideal_ph_min is not None and self.ideal_ph_max is not None and self.ideal_ph_min > self.ideal_ph_max:
            raise ValueError("ideal_ph_min must be less than or equal to ideal_ph_max.")
        if (
            self.tolerable_ph_min is not None
            and self.tolerable_ph_max is not None
            and self.tolerable_ph_min > self.tolerable_ph_max
        ):
            raise ValueError("tolerable_ph_min must be less than or equal to tolerable_ph_max.")
        if (
            self.tolerable_ph_min is not None
            and self.ideal_ph_min is not None
            and self.tolerable_ph_min > self.ideal_ph_min
        ):
            raise ValueError("tolerable_ph_min must be less than or equal to ideal_ph_min.")
        if (
            self.ideal_ph_max is not None
            and self.tolerable_ph_max is not None
            and self.ideal_ph_max > self.tolerable_ph_max
        ):
            raise ValueError("ideal_ph_max must be less than or equal to tolerable_ph_max.")
        if (
            self.optimal_temp_min_c is not None
            and self.optimal_temp_max_c is not None
            and self.optimal_temp_min_c > self.optimal_temp_max_c
        ):
            raise ValueError("optimal_temp_min_c must be less than or equal to optimal_temp_max_c.")
        if (
            self.tolerable_temp_min_c is not None
            and self.tolerable_temp_max_c is not None
            and self.tolerable_temp_min_c > self.tolerable_temp_max_c
        ):
            raise ValueError("tolerable_temp_min_c must be less than or equal to tolerable_temp_max_c.")
        if (
            self.tolerable_temp_min_c is not None
            and self.optimal_temp_min_c is not None
            and self.tolerable_temp_min_c > self.optimal_temp_min_c
        ):
            raise ValueError("tolerable_temp_min_c must be less than or equal to optimal_temp_min_c.")
        if (
            self.optimal_temp_max_c is not None
            and self.tolerable_temp_max_c is not None
            and self.optimal_temp_max_c > self.tolerable_temp_max_c
        ):
            raise ValueError("optimal_temp_max_c must be less than or equal to tolerable_temp_max_c.")
        if (
            self.preferred_rainfall_min_mm is not None
            and self.preferred_rainfall_max_mm is not None
            and self.preferred_rainfall_min_mm > self.preferred_rainfall_max_mm
        ):
            raise ValueError("preferred_rainfall_min_mm must be less than or equal to preferred_rainfall_max_mm.")
        seen_stage_names: set[str] = set()
        for stage in self.growth_stages:
            normalized_name = stage.name.casefold()
            if normalized_name in seen_stage_names:
                raise ValueError("growth_stages must contain unique stage names.")
            seen_stage_names.add(normalized_name)
        return self


class CropProfileCreate(CropProfileBase):
    """Schema used when creating a crop profile."""

    crop_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("crop_name", "name"),
    )
    ideal_ph_min: float = Field(
        ...,
        ge=0,
        le=14,
        validation_alias=AliasChoices("ideal_ph_min", "optimal_ph_min"),
    )
    ideal_ph_max: float = Field(
        ...,
        ge=0,
        le=14,
        validation_alias=AliasChoices("ideal_ph_max", "optimal_ph_max"),
    )
    tolerable_ph_min: float = Field(
        ...,
        ge=0,
        le=14,
        validation_alias=AliasChoices("tolerable_ph_min", "min_ph"),
    )
    tolerable_ph_max: float = Field(
        ...,
        ge=0,
        le=14,
        validation_alias=AliasChoices("tolerable_ph_max", "max_ph"),
    )
    water_requirement_level: WaterRequirementLevel = Field(
        ...,
        validation_alias=AliasChoices("water_requirement_level", "water_requirement"),
    )
    drainage_requirement: CropDrainageRequirement
    frost_sensitivity: CropSensitivityLevel
    heat_sensitivity: CropSensitivityLevel


class CropProfileUpdate(CropProfileBase):
    """Schema used when partially updating an existing crop profile."""


class CropProfileRead(BaseModel):
    """Schema returned for crop profile read operations."""

    model_config = ConfigDict(from_attributes=True)

    id: int | str | UUID
    crop_name: str
    scientific_name: str | None
    ideal_ph_min: float
    ideal_ph_max: float
    tolerable_ph_min: float
    tolerable_ph_max: float
    water_requirement_level: WaterRequirementLevel
    drainage_requirement: CropDrainageRequirement
    frost_sensitivity: CropSensitivityLevel
    heat_sensitivity: CropSensitivityLevel
    salinity_tolerance: CropPreferenceLevel | None
    rooting_depth_cm: float | None
    slope_tolerance: float | None
    optimal_temp_min_c: float | None
    optimal_temp_max_c: float | None
    tolerable_temp_min_c: float | None
    tolerable_temp_max_c: float | None
    rainfall_requirement_mm: float | None
    preferred_rainfall_min_mm: float | None
    preferred_rainfall_max_mm: float | None
    frost_tolerance_days: int | None
    heat_tolerance_days: int | None
    target_nitrogen_ppm: float | None
    target_phosphorus_ppm: float | None
    target_potassium_ppm: float | None
    organic_matter_preference: CropPreferenceLevel | None
    notes: str | None
    growth_stages: list[GrowthStageDefinition] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
