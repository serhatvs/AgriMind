def test_create_soil_test(client, created_field):
    """Test that a soil test can be created for a field and returns correct data."""
    soil_data = {
        "field_id": created_field["id"],
        "ph_level": 6.5,
        "nitrogen_ppm": 45.0,
        "phosphorus_ppm": 30.0,
        "potassium_ppm": 200.0,
        "organic_matter_percent": 3.5,
        "soil_texture": "loamy",
    }
    response = client.post("/api/v1/soil-tests/", json=soil_data)
    assert response.status_code == 201
    data = response.json()
    assert data["field_id"] == created_field["id"]
    assert data["ph_level"] == 6.5


def test_list_soil_tests(client, created_field):
    """Test that the list endpoint returns all soil tests including newly created ones."""
    soil_data = {
        "field_id": created_field["id"],
        "ph_level": 6.0,
        "nitrogen_ppm": 40.0,
        "phosphorus_ppm": 25.0,
        "potassium_ppm": 180.0,
        "organic_matter_percent": 3.0,
        "soil_texture": "sandy",
    }
    client.post("/api/v1/soil-tests/", json=soil_data)
    response = client.get("/api/v1/soil-tests/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_soil_tests_for_field(client, created_field):
    """Test that soil tests can be retrieved filtered by a specific field id."""
    soil_data = {
        "field_id": created_field["id"],
        "ph_level": 6.5,
        "nitrogen_ppm": 45.0,
        "phosphorus_ppm": 30.0,
        "potassium_ppm": 200.0,
        "organic_matter_percent": 3.5,
        "soil_texture": "loamy",
    }
    client.post("/api/v1/soil-tests/", json=soil_data)
    field_id = created_field["id"]
    response = client.get(f"/api/v1/soil-tests/field/{field_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["field_id"] == field_id
