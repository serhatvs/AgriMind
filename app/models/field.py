from datetime import datetime, timezone
from sqlalchemy import Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Field(Base):
    __tablename__ = "fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    area_hectares: Mapped[float] = mapped_column(Float, nullable=False)
    slope_percent: Mapped[float] = mapped_column(Float, default=0.0)
    irrigation_available: Mapped[bool] = mapped_column(Boolean, default=False)
    drainage_quality: Mapped[str] = mapped_column(String, default="moderate")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    soil_tests = relationship("SoilTest", back_populates="field")
