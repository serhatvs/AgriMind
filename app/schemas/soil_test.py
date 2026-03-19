from datetime import datetime
from pydantic import BaseModel


class SoilTestCreate(BaseModel):
    field_id: int
    ph_level: float
    nitrogen_ppm: float
    phosphorus_ppm: float
    potassium_ppm: float
    organic_matter_percent: float
    soil_texture: str
    tested_at: datetime | None = None


class SoilTestRead(BaseModel):
    id: int
    field_id: int
    ph_level: float
    nitrogen_ppm: float
    phosphorus_ppm: float
    potassium_ppm: float
    organic_matter_percent: float
    soil_texture: str
    tested_at: datetime

    model_config = {"from_attributes": True}
