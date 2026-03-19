"""Pydantic schemas for soil test input and output contracts."""

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class SoilTestBase(BaseModel):
    """Shared soil test attributes and validation rules."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )

    field_id: int | None = Field(default=None, gt=0)
    sample_date: datetime | None = Field(
        default=None,
        validation_alias=AliasChoices("sample_date", "tested_at"),
    )
    ph: float | None = Field(
        default=None,
        ge=0,
        le=14,
        validation_alias=AliasChoices("ph", "ph_level"),
    )
    ec: float | None = Field(default=None, ge=0)
    organic_matter_percent: float | None = Field(default=None, ge=0, le=100)
    nitrogen_ppm: float | None = Field(default=None, ge=0)
    phosphorus_ppm: float | None = Field(default=None, ge=0)
    potassium_ppm: float | None = Field(default=None, ge=0)
    calcium_ppm: float | None = Field(default=None, ge=0)
    magnesium_ppm: float | None = Field(default=None, ge=0)
    texture_class: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        validation_alias=AliasChoices("texture_class", "soil_texture"),
    )
    drainage_class: str | None = Field(default=None, min_length=1, max_length=32)
    depth_cm: float | None = Field(default=None, gt=0)
    water_holding_capacity: float | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator("texture_class", "drainage_class")
    @classmethod
    def validate_non_empty_strings(cls, value: str | None) -> str | None:
        """Reject blank strings for categorical soil fields."""

        if value is None:
            return value
        if not value:
            raise ValueError("Value must not be empty.")
        return value

    @field_validator("notes")
    @classmethod
    def normalize_notes(cls, value: str | None) -> str | None:
        """Normalize blank notes to null."""

        if value == "":
            return None
        return value


class SoilTestCreate(SoilTestBase):
    """Schema used when creating a soil test."""

    field_id: int = Field(..., gt=0)
    ph: float = Field(..., ge=0, le=14, validation_alias=AliasChoices("ph", "ph_level"))
    organic_matter_percent: float = Field(..., ge=0, le=100)
    nitrogen_ppm: float = Field(..., ge=0)
    phosphorus_ppm: float = Field(..., ge=0)
    potassium_ppm: float = Field(..., ge=0)
    texture_class: str = Field(
        ...,
        min_length=1,
        max_length=64,
        validation_alias=AliasChoices("texture_class", "soil_texture"),
    )


class SoilTestUpdate(SoilTestBase):
    """Schema used when partially updating an existing soil test."""


class SoilTestRead(BaseModel):
    """Schema returned for soil test read operations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    field_id: int
    sample_date: datetime
    ph: float
    ec: float | None
    organic_matter_percent: float
    nitrogen_ppm: float
    phosphorus_ppm: float
    potassium_ppm: float
    calcium_ppm: float | None
    magnesium_ppm: float | None
    texture_class: str
    drainage_class: str | None
    depth_cm: float | None
    water_holding_capacity: float | None
    notes: str | None
    created_at: datetime
