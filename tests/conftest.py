import os

SQLALCHEMY_DATABASE_URL = "sqlite://"
os.environ.setdefault("DATABASE_URL", SQLALCHEMY_DATABASE_URL)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_field_data():
    return {
        "name": "Test Field",
        "location_name": "Springfield",
        "latitude": 39.7817,
        "longitude": -89.6501,
        "area_hectares": 10.0,
        "elevation_meters": 182.0,
        "slope_percent": 3.0,
        "aspect": "south",
        "irrigation_available": True,
        "water_source_type": "well",
        "infrastructure_score": 72,
        "drainage_quality": "good",
        "notes": "Primary test parcel",
    }


@pytest.fixture
def sample_soil_data(created_field):
    return {
        "field_id": created_field["id"],
        "sample_date": "2026-03-15T10:00:00Z",
        "ph": 6.5,
        "ec": 0.8,
        "nitrogen_ppm": 45.0,
        "phosphorus_ppm": 30.0,
        "potassium_ppm": 200.0,
        "calcium_ppm": 1700.0,
        "magnesium_ppm": 210.0,
        "organic_matter_percent": 3.5,
        "texture_class": "loamy",
        "drainage_class": "good",
        "depth_cm": 30.0,
        "water_holding_capacity": 21.5,
        "notes": "Baseline sample",
    }


@pytest.fixture
def created_field(client, sample_field_data):
    response = client.post("/api/v1/fields/", json=sample_field_data)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_crop_data():
    return {
        "crop_name": "Wheat",
        "scientific_name": "Triticum aestivum",
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 7.0,
        "tolerable_ph_min": 5.5,
        "tolerable_ph_max": 7.5,
        "water_requirement_level": "medium",
        "drainage_requirement": "good",
        "frost_sensitivity": "medium",
        "heat_sensitivity": "medium",
        "salinity_tolerance": "low",
        "rooting_depth_cm": 120.0,
        "slope_tolerance": 10.0,
        "optimal_temp_min_c": 12.0,
        "optimal_temp_max_c": 22.0,
        "rainfall_requirement_mm": 450.0,
        "frost_tolerance_days": 25,
        "heat_tolerance_days": 18,
        "organic_matter_preference": "moderate",
        "notes": "Benchmark cereal profile",
    }


@pytest.fixture
def sample_growth_stages():
    return [
        {
            "name": "germination",
            "duration_days": 7,
            "irrigation_need": "medium",
            "fertilizer_need": "low",
        },
        {
            "name": "vegetative",
            "duration_days": 21,
            "irrigation_need": "high",
            "fertilizer_need": "medium",
        },
        {
            "name": "reproductive",
            "duration_days": 14,
            "irrigation_need": "medium",
            "fertilizer_need": "high",
        },
    ]


@pytest.fixture
def created_crop(client, sample_crop_data):
    response = client.post("/api/v1/crops/", json=sample_crop_data)
    assert response.status_code == 201
    return response.json()
