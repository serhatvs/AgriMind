"""Register ORM model modules with the shared SQLAlchemy metadata."""

from app.models import (
    crop_price,
    crop_profile,
    feedback,
    field,
    field_crop_cycle,
    input_cost,
    recommendation,
    soil_test,
    weather_history,
)

__all__ = [
    "crop_price",
    "crop_profile",
    "feedback",
    "field",
    "field_crop_cycle",
    "input_cost",
    "recommendation",
    "soil_test",
    "weather_history",
]
