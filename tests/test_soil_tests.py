from app.services.soil_service import get_latest_soil_test_for_field


def test_create_soil_test(client, created_field):
    """Test that a soil test can be created for a field and returns correct data."""
    soil_data = {
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
    }
    response = client.post("/api/v1/soil-tests/", json=soil_data)
    assert response.status_code == 201
    data = response.json()
    assert data["field_id"] == created_field["id"]
    assert data["ph"] == 6.5
    assert data["texture_class"] == "loamy"
    assert "created_at" in data


def test_list_soil_tests(client, created_field):
    """Test that the list endpoint returns all soil tests including newly created ones."""
    soil_data = {
        "field_id": created_field["id"],
        "ph": 6.0,
        "nitrogen_ppm": 40.0,
        "phosphorus_ppm": 25.0,
        "potassium_ppm": 180.0,
        "organic_matter_percent": 3.0,
        "texture_class": "sandy",
    }
    client.post("/api/v1/soil-tests/", json=soil_data)
    response = client.get("/api/v1/soil-tests/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_soil_tests_for_field(client, created_field):
    """Test that soil tests can be retrieved filtered by a specific field id."""
    soil_data = {
        "field_id": created_field["id"],
        "ph": 6.5,
        "nitrogen_ppm": 45.0,
        "phosphorus_ppm": 30.0,
        "potassium_ppm": 200.0,
        "organic_matter_percent": 3.5,
        "texture_class": "loamy",
    }
    client.post("/api/v1/soil-tests/", json=soil_data)
    field_id = created_field["id"]
    response = client.get(f"/api/v1/soil-tests/field/{field_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["field_id"] == field_id
    assert data[0]["texture_class"] == "loamy"


def test_create_soil_test_accepts_legacy_aliases(client, created_field):
    """Test that legacy field names still map to the canonical soil contract."""
    soil_data = {
        "field_id": created_field["id"],
        "tested_at": "2026-03-15T10:00:00Z",
        "ph_level": 6.4,
        "nitrogen_ppm": 42.0,
        "phosphorus_ppm": 26.0,
        "potassium_ppm": 190.0,
        "organic_matter_percent": 3.2,
        "soil_texture": "silty",
    }
    response = client.post("/api/v1/soil-tests/", json=soil_data)
    assert response.status_code == 201
    data = response.json()
    assert data["ph"] == 6.4
    assert data["texture_class"] == "silty"
    assert data["sample_date"].startswith("2026-03-15T10:00:00")


def test_create_soil_test_rejects_missing_field(client):
    response = client.post(
        "/api/v1/soil-tests/",
        json={
            "field_id": 9999,
            "ph": 6.5,
            "nitrogen_ppm": 45.0,
            "phosphorus_ppm": 30.0,
            "potassium_ppm": 200.0,
            "organic_matter_percent": 3.5,
            "texture_class": "loamy",
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Field with id 9999 not found"


def test_update_soil_test(client, sample_soil_data):
    created = client.post("/api/v1/soil-tests/", json=sample_soil_data)
    soil_test_id = created.json()["id"]

    response = client.put(
        f"/api/v1/soil-tests/{soil_test_id}",
        json={
            "ph_level": 6.9,
            "soil_texture": "clay",
            "tested_at": "2026-03-18T09:30:00Z",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ph"] == 6.9
    assert data["texture_class"] == "clay"
    assert data["sample_date"].startswith("2026-03-18T09:30:00")


def test_update_soil_test_not_found(client):
    response = client.put(
        "/api/v1/soil-tests/9999",
        json={"ph": 6.3},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Soil test not found"


def test_update_soil_test_rejects_missing_field(client, sample_soil_data):
    created = client.post("/api/v1/soil-tests/", json=sample_soil_data)
    soil_test_id = created.json()["id"]

    response = client.put(
        f"/api/v1/soil-tests/{soil_test_id}",
        json={"field_id": 9999},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Field with id 9999 not found"


def test_update_soil_test_can_change_latest_record_ordering(client, db, created_field):
    field_id = created_field["id"]
    older_response = client.post(
        "/api/v1/soil-tests/",
        json={
            "field_id": field_id,
            "sample_date": "2026-03-10T10:00:00Z",
            "ph": 6.1,
            "nitrogen_ppm": 40.0,
            "phosphorus_ppm": 25.0,
            "potassium_ppm": 170.0,
            "organic_matter_percent": 2.8,
            "texture_class": "sandy",
        },
    )
    newer_response = client.post(
        "/api/v1/soil-tests/",
        json={
            "field_id": field_id,
            "sample_date": "2026-03-12T10:00:00Z",
            "ph": 6.4,
            "nitrogen_ppm": 44.0,
            "phosphorus_ppm": 29.0,
            "potassium_ppm": 190.0,
            "organic_matter_percent": 3.1,
            "texture_class": "loamy",
        },
    )

    assert older_response.status_code == 201
    assert newer_response.status_code == 201
    assert get_latest_soil_test_for_field(db, field_id).id == newer_response.json()["id"]

    response = client.put(
        f"/api/v1/soil-tests/{older_response.json()['id']}",
        json={"sample_date": "2026-03-20T10:00:00Z"},
    )

    assert response.status_code == 200
    assert get_latest_soil_test_for_field(db, field_id).id == older_response.json()["id"]
