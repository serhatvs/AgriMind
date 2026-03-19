def test_rank_fields(client):
    """Test that two fields are ranked correctly, with the better-suited field placed first."""
    # Create two fields
    field1 = client.post("/api/v1/fields/", json={
        "name": "Field Alpha",
        "location": "Zone A",
        "area_hectares": 15.0,
        "slope_percent": 2.0,
        "irrigation_available": True,
        "drainage_quality": "excellent",
    }).json()
    field2 = client.post("/api/v1/fields/", json={
        "name": "Field Beta",
        "location": "Zone B",
        "area_hectares": 8.0,
        "slope_percent": 8.0,
        "irrigation_available": False,
        "drainage_quality": "poor",
    }).json()

    # Soil tests
    client.post("/api/v1/soil-tests/", json={
        "field_id": field1["id"],
        "ph_level": 6.5,
        "nitrogen_ppm": 50.0,
        "phosphorus_ppm": 35.0,
        "potassium_ppm": 220.0,
        "organic_matter_percent": 4.0,
        "soil_texture": "loamy",
    })
    client.post("/api/v1/soil-tests/", json={
        "field_id": field2["id"],
        "ph_level": 5.0,
        "nitrogen_ppm": 10.0,
        "phosphorus_ppm": 5.0,
        "potassium_ppm": 60.0,
        "organic_matter_percent": 1.0,
        "soil_texture": "sandy",
    })

    # Create crop
    crop = client.post("/api/v1/crops/", json={
        "name": "Corn",
        "min_ph": 5.8,
        "max_ph": 7.0,
        "optimal_ph_min": 6.0,
        "optimal_ph_max": 6.8,
        "min_nitrogen_ppm": 40.0,
        "min_phosphorus_ppm": 25.0,
        "min_potassium_ppm": 180.0,
        "water_requirement": "high",
        "drainage_requirement": "moderate",
        "preferred_soil_textures": "loamy,silty",
        "min_area_hectares": 2.0,
        "max_slope_percent": 5.0,
    }).json()

    response = client.post("/api/v1/rank-fields/", json={
        "field_ids": [field1["id"], field2["id"]],
        "crop_id": crop["id"],
        "top_n": 5,
    })
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["rank"] == 1
    # field1 should score higher
    assert data[0]["field_id"] == field1["id"]
    assert data[0]["score"] > data[1]["score"]


def test_rank_fields_invalid_crop(client):
    """Test that ranking with a non-existent crop id returns a 404 response."""
    response = client.post("/api/v1/rank-fields/", json={
        "field_ids": [1],
        "crop_id": 9999,
        "top_n": 5,
    })
    assert response.status_code == 404


def test_rank_fields_penalizes_fields_below_minimum_area(client):
    """Test that fields below the crop minimum area fall behind otherwise similar candidates."""
    small_field = client.post("/api/v1/fields/", json={
        "name": "Small Plot",
        "location": "Zone C",
        "area_hectares": 1.0,
        "slope_percent": 2.0,
        "irrigation_available": True,
        "drainage_quality": "excellent",
    }).json()
    large_field = client.post("/api/v1/fields/", json={
        "name": "Large Plot",
        "location": "Zone D",
        "area_hectares": 5.0,
        "slope_percent": 2.0,
        "irrigation_available": True,
        "drainage_quality": "excellent",
    }).json()

    for field in (small_field, large_field):
        client.post("/api/v1/soil-tests/", json={
            "field_id": field["id"],
            "ph_level": 6.5,
            "nitrogen_ppm": 50.0,
            "phosphorus_ppm": 35.0,
            "potassium_ppm": 220.0,
            "organic_matter_percent": 4.0,
            "soil_texture": "loamy",
        })

    crop = client.post("/api/v1/crops/", json={
        "name": "Blackberry",
        "min_ph": 5.5,
        "max_ph": 6.8,
        "optimal_ph_min": 5.8,
        "optimal_ph_max": 6.5,
        "min_nitrogen_ppm": 40.0,
        "min_phosphorus_ppm": 25.0,
        "min_potassium_ppm": 180.0,
        "water_requirement": "high",
        "drainage_requirement": "good",
        "preferred_soil_textures": "loamy,silty",
        "min_area_hectares": 2.0,
        "max_slope_percent": 5.0,
    }).json()

    response = client.post("/api/v1/rank-fields/", json={
        "field_ids": [small_field["id"], large_field["id"]],
        "crop_id": crop["id"],
        "top_n": 5,
    })

    assert response.status_code == 200
    data = response.json()
    assert data[0]["field_id"] == large_field["id"]
    assert data[1]["field_id"] == small_field["id"]
    assert data[1]["score"] == 0.0
    assert "below the minimum 2 ha" in data[1]["explanation"]
