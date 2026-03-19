"""Pydantic schemas for crop agronomic requirement profiles."""

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import (
    CropDrainageRequirement,
    CropPreferenceLevel,
    CropSensitivityLevel,
    WaterRequirementLevel,
)


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
    organic_matter_preference: CropPreferenceLevel | None = None
    notes: str | None = None

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

    id: int
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
    organic_matter_preference: CropPreferenceLevel | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
