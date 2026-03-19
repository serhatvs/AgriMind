def test_create_field(client, sample_field_data):
    """Test that a field can be created and returns the correct data with an assigned id."""
    response = client.post("/api/v1/fields/", json=sample_field_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_field_data["name"]
    assert data["location_name"] == sample_field_data["location_name"]
    assert data["latitude"] == sample_field_data["latitude"]
    assert data["area_hectares"] == sample_field_data["area_hectares"]
    assert data["infrastructure_score"] == sample_field_data["infrastructure_score"]
    assert "id" in data


def test_list_fields(client, created_field):
    """Test that listing fields returns at least the one field that was created."""
    response = client.get("/api/v1/fields/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_field(client, created_field):
    """Test that a field can be retrieved by its id."""
    field_id = created_field["id"]
    response = client.get(f"/api/v1/fields/{field_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == field_id
    assert data["location_name"] == created_field["location_name"]


def test_get_field_not_found(client):
    """Test that requesting a non-existent field id returns a 404 response."""
    response = client.get("/api/v1/fields/9999")
    assert response.status_code == 404


def test_update_field(client, created_field):
    """Test that a field's name can be updated via the PUT endpoint."""
    field_id = created_field["id"]
    response = client.put(
        f"/api/v1/fields/{field_id}",
        json={"name": "Updated Field", "infrastructure_score": 90},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Field"
    assert response.json()["infrastructure_score"] == 90


def test_create_field_accepts_legacy_location_alias(client, sample_field_data):
    """Test that the deprecated location alias still maps to location_name."""
    legacy_payload = dict(sample_field_data)
    legacy_payload["location"] = legacy_payload.pop("location_name")
    response = client.post("/api/v1/fields/", json=legacy_payload)
    assert response.status_code == 201
    assert response.json()["location_name"] == "Springfield"


def test_delete_field(client, created_field):
    """Test that deleting a field removes it and subsequent GET returns 404."""
    field_id = created_field["id"]
    response = client.delete(f"/api/v1/fields/{field_id}")
    assert response.status_code == 204
    response = client.get(f"/api/v1/fields/{field_id}")
    assert response.status_code == 404
