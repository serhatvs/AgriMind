from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class FieldCreate(BaseModel):
    name: str
    location: str
    area_hectares: float
    slope_percent: float = 0.0
    irrigation_available: bool = False
    drainage_quality: str = "moderate"


class FieldUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    area_hectares: Optional[float] = None
    slope_percent: Optional[float] = None
    irrigation_available: Optional[bool] = None
    drainage_quality: Optional[str] = None


class FieldRead(BaseModel):
    id: int
    name: str
    location: str
    area_hectares: float
    slope_percent: float
    irrigation_available: bool
    drainage_quality: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
