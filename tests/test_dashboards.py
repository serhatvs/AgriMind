def test_get_dashboard_returns_empty_state(client):
    response = client.get("/api/v1/dashboards/")

    assert response.status_code == 200
    assert response.json() == {
        "totals": {
            "fields": 0,
            "soil_tests": 0,
            "crop_profiles": 0,
        },
        "coverage": {
            "fields_with_soil_tests": 0,
            "fields_without_soil_tests": 0,
        },
        "recent_fields": [],
        "recent_soil_tests": [],
        "recent_crop_profiles": [],
    }


def test_get_dashboard_returns_populated_overview(client, sample_field_data, sample_crop_data):
    first_field_payload = dict(sample_field_data)
    first_field_payload["name"] = "Field Alpha"
    first_field_payload["location_name"] = "Alpha Plains"
    first_field_response = client.post("/api/v1/fields/", json=first_field_payload)
    assert first_field_response.status_code == 201

    second_field_payload = dict(sample_field_data)
    second_field_payload["name"] = "Field Beta"
    second_field_payload["location_name"] = "Beta Plains"
    second_field_payload["latitude"] = 38.991
    second_field_payload["longitude"] = -89.412
    second_field_response = client.post("/api/v1/fields/", json=second_field_payload)
    assert second_field_response.status_code == 201

    wheat_payload = dict(sample_crop_data)
    wheat_payload["crop_name"] = "Wheat"
    wheat_response = client.post("/api/v1/crop-profiles/", json=wheat_payload)
    assert wheat_response.status_code == 201

    corn_payload = dict(sample_crop_data)
    corn_payload["crop_name"] = "Corn"
    corn_payload["scientific_name"] = "Zea mays"
    corn_response = client.post("/api/v1/crop-profiles/", json=corn_payload)
    assert corn_response.status_code == 201

    field_alpha_id = first_field_response.json()["id"]
    soil_one_response = client.post(
        "/api/v1/soil-tests/",
        json={
            "field_id": field_alpha_id,
            "sample_date": "2026-03-15T10:00:00Z",
            "ph": 6.3,
            "nitrogen_ppm": 42.0,
            "phosphorus_ppm": 28.0,
            "potassium_ppm": 195.0,
            "organic_matter_percent": 3.2,
            "texture_class": "loamy",
        },
    )
    soil_two_response = client.post(
        "/api/v1/soil-tests/",
        json={
            "field_id": field_alpha_id,
            "sample_date": "2026-03-20T10:00:00Z",
            "ph": 6.5,
            "nitrogen_ppm": 47.0,
            "phosphorus_ppm": 31.0,
            "potassium_ppm": 205.0,
            "organic_matter_percent": 3.6,
            "texture_class": "clay loam",
        },
    )
    assert soil_one_response.status_code == 201
    assert soil_two_response.status_code == 201

    response = client.get("/api/v1/dashboards/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"] == {
        "fields": 2,
        "soil_tests": 2,
        "crop_profiles": 2,
    }
    assert payload["coverage"] == {
        "fields_with_soil_tests": 1,
        "fields_without_soil_tests": 1,
    }
    assert [item["name"] for item in payload["recent_fields"]] == ["Field Beta", "Field Alpha"]
    assert payload["recent_soil_tests"][0]["field_name"] == "Field Alpha"
    assert payload["recent_soil_tests"][0]["sample_date"].startswith("2026-03-20T10:00:00")
    assert [item["crop_name"] for item in payload["recent_crop_profiles"]] == ["Corn", "Wheat"]
