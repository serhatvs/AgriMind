from pydantic import BaseModel
from typing import Optional


class CropProfileCreate(BaseModel):
    name: str
    variety: Optional[str] = None
    min_ph: float
    max_ph: float
    optimal_ph_min: float
    optimal_ph_max: float
    min_nitrogen_ppm: float
    min_phosphorus_ppm: float
    min_potassium_ppm: float
    water_requirement: str
    drainage_requirement: str
    preferred_soil_textures: str
    min_area_hectares: float = 0.0
    max_slope_percent: float = 15.0


class CropProfileRead(BaseModel):
    id: int
    name: str
    variety: Optional[str]
    min_ph: float
    max_ph: float
    optimal_ph_min: float
    optimal_ph_max: float
    min_nitrogen_ppm: float
    min_phosphorus_ppm: float
    min_potassium_ppm: float
    water_requirement: str
    drainage_requirement: str
    preferred_soil_textures: str
    min_area_hectares: float
    max_slope_percent: float

    model_config = {"from_attributes": True}
