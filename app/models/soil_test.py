from datetime import datetime, timezone
from sqlalchemy import Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SoilTest(Base):
    __tablename__ = "soil_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    field_id: Mapped[int] = mapped_column(Integer, ForeignKey("fields.id"), nullable=False)
    ph_level: Mapped[float] = mapped_column(Float, nullable=False)
    nitrogen_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    phosphorus_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    potassium_ppm: Mapped[float] = mapped_column(Float, nullable=False)
    organic_matter_percent: Mapped[float] = mapped_column(Float, nullable=False)
    soil_texture: Mapped[str] = mapped_column(String, nullable=False)
    tested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    field = relationship("Field", back_populates="soil_tests")
