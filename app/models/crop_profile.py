from sqlalchemy import Integer, String, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CropProfile(Base):
    __tablename__ = "crop_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    variety: Mapped[str | None] = mapped_column(String, nullable=True)
    min_ph: Mapped[float] = mapped_column(Float, nullable=False)
    max_ph: Mapped[float] = mapped_column(Float, nullable=False)
    optimal_ph_min: Mapped[float] = mapped_column(Float, nullable=False)
    optimal_ph_max: Mapped[float] = mapped_column(Float, nullable=False)
    min_nitrogen_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    min_phosphorus_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    min_potassium_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    water_requirement: Mapped[str] = mapped_column(String, nullable=False)
    drainage_requirement: Mapped[str] = mapped_column(String, nullable=False)
    preferred_soil_textures: Mapped[str] = mapped_column(String, nullable=False)
    min_area_hectares: Mapped[float] = mapped_column(Float, default=0.0)
    max_slope_percent: Mapped[float] = mapped_column(Float, default=15.0)
