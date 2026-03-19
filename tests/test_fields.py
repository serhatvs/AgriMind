def test_create_field(client, sample_field_data):
    response = client.post("/api/v1/fields/", json=sample_field_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == sample_field_data["name"]
    assert data["area_hectares"] == sample_field_data["area_hectares"]
    assert "id" in data


def test_list_fields(client, created_field):
    response = client.get("/api/v1/fields/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


def test_get_field(client, created_field):
    field_id = created_field["id"]
    response = client.get(f"/api/v1/fields/{field_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == field_id


def test_get_field_not_found(client):
    response = client.get("/api/v1/fields/9999")
    assert response.status_code == 404


def test_update_field(client, created_field):
    field_id = created_field["id"]
    response = client.put(f"/api/v1/fields/{field_id}", json={"name": "Updated Field"})
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Field"


def test_delete_field(client, created_field):
    field_id = created_field["id"]
    response = client.delete(f"/api/v1/fields/{field_id}")
    assert response.status_code == 204
    response = client.get(f"/api/v1/fields/{field_id}")
    assert response.status_code == 404
