import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.main import app

SQLALCHEMY_DATABASE_URL = "sqlite://"

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
        "location": "Springfield",
        "area_hectares": 10.0,
        "slope_percent": 3.0,
        "irrigation_available": True,
        "drainage_quality": "good",
    }


@pytest.fixture
def sample_soil_data(created_field):
    return {
        "field_id": created_field["id"],
        "ph_level": 6.5,
        "nitrogen_ppm": 45.0,
        "phosphorus_ppm": 30.0,
        "potassium_ppm": 200.0,
        "organic_matter_percent": 3.5,
        "soil_texture": "loamy",
    }


@pytest.fixture
def created_field(client, sample_field_data):
    response = client.post("/api/v1/fields/", json=sample_field_data)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_crop_data():
    return {
        "name": "Wheat",
        "variety": "Winter",
        "min_ph": 5.5,
        "max_ph": 7.5,
        "optimal_ph_min": 6.0,
        "optimal_ph_max": 7.0,
        "min_nitrogen_ppm": 30.0,
        "min_phosphorus_ppm": 20.0,
        "min_potassium_ppm": 150.0,
        "water_requirement": "medium",
        "drainage_requirement": "good",
        "preferred_soil_textures": "loamy,silty",
        "min_area_hectares": 1.0,
        "max_slope_percent": 10.0,
    }


@pytest.fixture
def created_crop(client, sample_crop_data):
    response = client.post("/api/v1/crops/", json=sample_crop_data)
    assert response.status_code == 201
    return response.json()
