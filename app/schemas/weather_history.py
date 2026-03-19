"""Pydantic schemas for weather history input and climate summaries."""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeatherHistoryBase(BaseModel):
    """Shared weather-history attributes and validation rules."""

    model_config = ConfigDict(
        extra="forbid",
        from_attributes=True,
    )

    field_id: int | None = Field(default=None, gt=0)
    date: date_type | None = None
    min_temp: float | None = None
    max_temp: float | None = None
    avg_temp: float | None = None
    rainfall_mm: float | None = Field(default=None, ge=0)
    humidity: float | None = Field(default=None, ge=0, le=100)
    wind_speed: float | None = Field(default=None, ge=0)
    solar_radiation: float | None = Field(default=None, ge=0)
    et0: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_temperature_order(self) -> "WeatherHistoryBase":
        """Ensure min, average, and max temperatures follow a logical order."""

        if self.min_temp is None or self.avg_temp is None or self.max_temp is None:
            return self
        if self.min_temp > self.avg_temp or self.avg_temp > self.max_temp:
            raise ValueError("Temperature values must satisfy min_temp <= avg_temp <= max_temp.")
        return self


class WeatherHistoryCreate(WeatherHistoryBase):
    """Schema used when creating a weather history record."""

    field_id: int = Field(..., gt=0)
    date: date_type
    min_temp: float
    max_temp: float
    avg_temp: float
    rainfall_mm: float = Field(..., ge=0)
    humidity: float = Field(..., ge=0, le=100)
    wind_speed: float = Field(..., ge=0)


class WeatherHistoryRead(BaseModel):
    """Schema returned for weather-history read operations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    field_id: int
    date: date_type
    min_temp: float
    max_temp: float
    avg_temp: float
    rainfall_mm: float
    humidity: float
    wind_speed: float
    solar_radiation: float | None
    et0: float | None
    created_at: datetime


class ClimateSummary(BaseModel):
    """Aggregated climate metrics for a field over a recent time window."""

    avg_temp: float
    total_rainfall: float
    frost_days: int
    heat_days: int
