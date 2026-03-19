"""Pydantic schemas for field input and output contracts."""

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.models.enums import FieldAspect, WaterSourceType


class FieldBase(BaseModel):
    """Shared mutable field attributes and validation rules."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    name: str | None = Field(default=None, min_length=1, max_length=255)
    location_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("location_name", "location"),
    )
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    area_hectares: float | None = Field(default=None, gt=0)
    elevation_meters: float | None = None
    slope_percent: float | None = Field(default=None, ge=0, le=100)
    aspect: FieldAspect | None = None
    irrigation_available: bool | None = None
    water_source_type: WaterSourceType | None = None
    infrastructure_score: int | None = Field(default=None, ge=0, le=100)
    drainage_quality: str | None = Field(default=None, min_length=1, max_length=32)
    notes: str | None = None

    @field_validator("name", "location_name", "drainage_quality")
    @classmethod
    def validate_non_empty_strings(cls, value: str | None) -> str | None:
        """Reject blank strings for key field attributes."""

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


class FieldCreate(FieldBase):
    """Schema used when creating a field."""

    name: str = Field(..., min_length=1, max_length=255)
    location_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        validation_alias=AliasChoices("location_name", "location"),
    )
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    area_hectares: float = Field(..., gt=0)
    slope_percent: float = Field(default=0.0, ge=0, le=100)
    irrigation_available: bool = False
    infrastructure_score: int = Field(default=0, ge=0, le=100)
    drainage_quality: str = Field(default="moderate", min_length=1, max_length=32)


class FieldUpdate(FieldBase):
    """Schema used when partially updating an existing field."""


class FieldRead(BaseModel):
    """Schema returned for field read operations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    location_name: str
    latitude: float | None
    longitude: float | None
    area_hectares: float
    elevation_meters: float | None
    slope_percent: float
    aspect: FieldAspect | None
    irrigation_available: bool
    water_source_type: WaterSourceType | None
    infrastructure_score: int
    drainage_quality: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
