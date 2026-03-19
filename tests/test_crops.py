def test_create_crop(client, sample_crop_data):
    response = client.post("/api/v1/crops/", json=sample_crop_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Wheat"
    assert "id" in data


def test_list_crops(client, created_crop):
    response = client.get("/api/v1/crops/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_crop(client, created_crop):
    crop_id = created_crop["id"]
    response = client.get(f"/api/v1/crops/{crop_id}")
    assert response.status_code == 200
    assert response.json()["id"] == crop_id


def test_get_crop_not_found(client):
    response = client.get("/api/v1/crops/9999")
    assert response.status_code == 404
