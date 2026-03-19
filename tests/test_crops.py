def test_create_crop(client, sample_crop_data):
    """Test that a crop profile can be created and returns the correct data with an assigned id."""
    response = client.post("/api/v1/crops/", json=sample_crop_data)
    assert response.status_code == 201
    data = response.json()
    assert data["crop_name"] == "Wheat"
    assert data["water_requirement_level"] == "medium"
    assert "id" in data


def test_list_crops(client, created_crop):
    """Test that listing crop profiles returns at least the one crop that was created."""
    response = client.get("/api/v1/crops/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_get_crop(client, created_crop):
    """Test that a crop profile can be retrieved by its id."""
    crop_id = created_crop["id"]
    response = client.get(f"/api/v1/crops/{crop_id}")
    assert response.status_code == 200
    assert response.json()["id"] == crop_id
    assert response.json()["crop_name"] == created_crop["crop_name"]


def test_get_crop_not_found(client):
    """Test that requesting a non-existent crop id returns a 404 response."""
    response = client.get("/api/v1/crops/9999")
    assert response.status_code == 404


def test_create_crop_round_trips_growth_stages(client, sample_crop_data, sample_growth_stages):
    """Test that growth stage definitions persist through the crop API."""

    payload = {**sample_crop_data, "growth_stages": sample_growth_stages}
    response = client.post("/api/v1/crops/", json=payload)

    assert response.status_code == 201
    assert response.json()["growth_stages"] == sample_growth_stages


def test_crop_profile_alias_routes_round_trip_and_update(client, sample_crop_data):
    create_response = client.post("/api/v1/crop-profiles/", json=sample_crop_data)

    assert create_response.status_code == 201
    created = create_response.json()

    list_response = client.get("/api/v1/crop-profiles/")
    assert list_response.status_code == 200
    assert any(item["id"] == created["id"] for item in list_response.json())

    get_response = client.get(f"/api/v1/crop-profiles/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json()["crop_name"] == sample_crop_data["crop_name"]

    update_response = client.put(
        f"/api/v1/crop-profiles/{created['id']}",
        json={"crop_name": "Updated Wheat", "notes": "Alias route update"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["crop_name"] == "Updated Wheat"
    assert update_response.json()["notes"] == "Alias route update"

    legacy_response = client.get(f"/api/v1/crops/{created['id']}")
    assert legacy_response.status_code == 200
    assert legacy_response.json()["crop_name"] == "Updated Wheat"


def test_create_crop_profile_rejects_case_insensitive_duplicate_name(client, sample_crop_data):
    first_response = client.post("/api/v1/crop-profiles/", json=sample_crop_data)
    assert first_response.status_code == 201

    duplicate_payload = dict(sample_crop_data)
    duplicate_payload["crop_name"] = sample_crop_data["crop_name"].upper()
    duplicate_payload["scientific_name"] = "Duplicate Crop"

    duplicate_response = client.post("/api/v1/crop-profiles/", json=duplicate_payload)

    assert duplicate_response.status_code == 409
    assert "already exists" in duplicate_response.json()["detail"]


def test_update_crop_profile_rejects_case_insensitive_duplicate_name(client, sample_crop_data):
    wheat_response = client.post("/api/v1/crop-profiles/", json=sample_crop_data)
    assert wheat_response.status_code == 201

    corn_payload = dict(sample_crop_data)
    corn_payload["crop_name"] = "Corn"
    corn_payload["scientific_name"] = "Zea mays"
    corn_response = client.post("/api/v1/crop-profiles/", json=corn_payload)
    assert corn_response.status_code == 201

    update_response = client.put(
        f"/api/v1/crop-profiles/{corn_response.json()['id']}",
        json={"crop_name": "wHeAt"},
    )

    assert update_response.status_code == 409
    assert "already exists" in update_response.json()["detail"]


def test_update_crop_profile_not_found(client):
    response = client.put("/api/v1/crop-profiles/9999", json={"crop_name": "Missing"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Crop not found"
