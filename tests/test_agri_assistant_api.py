from app.config import settings
from app.services.agri_assistant_service import build_agri_assistant_context
from app.services.ranking_service import get_ranked_fields_response


def _create_field(client, name: str, **overrides) -> dict[str, object]:
    payload = {
        "name": name,
        "location_name": f"{name} Zone",
        "latitude": 39.0,
        "longitude": -94.0,
        "area_hectares": 10.0,
        "slope_percent": 3.0,
        "irrigation_available": True,
        "drainage_quality": "good",
    }
    payload.update(overrides)
    response = client.post("/api/v1/fields/", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_soil_test(client, field_id: int, **overrides) -> dict[str, object]:
    payload = {
        "field_id": field_id,
        "ph": 6.5,
        "organic_matter_percent": 4.0,
        "nitrogen_ppm": 50.0,
        "phosphorus_ppm": 35.0,
        "potassium_ppm": 220.0,
        "texture_class": "loamy",
        "depth_cm": 120.0,
        "ec": 1.2,
    }
    payload.update(overrides)
    response = client.post("/api/v1/soil-tests/", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_crop(client, **overrides) -> dict[str, object]:
    payload = {
        "crop_name": "Corn",
        "scientific_name": "Zea mays",
        "ideal_ph_min": 6.0,
        "ideal_ph_max": 6.8,
        "tolerable_ph_min": 5.8,
        "tolerable_ph_max": 7.0,
        "water_requirement_level": "medium",
        "drainage_requirement": "moderate",
        "frost_sensitivity": "high",
        "heat_sensitivity": "medium",
        "salinity_tolerance": "moderate",
        "rooting_depth_cm": 120.0,
        "slope_tolerance": 8.0,
        "organic_matter_preference": "moderate",
    }
    payload.update(overrides)
    response = client.post("/api/v1/crops/", json=payload)
    assert response.status_code == 201
    return response.json()


def test_agri_assistant_api_defaults_to_top_ranked_field_and_uses_fallback(client, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    field_alpha = _create_field(client, "Field Alpha")
    field_beta = _create_field(client, "Field Beta", irrigation_available=False, slope_percent=12.0)
    _create_soil_test(client, field_alpha["id"])
    _create_soil_test(client, field_beta["id"], ph=5.1, organic_matter_percent=1.0, depth_cm=60.0, ec=3.0)
    crop = _create_crop(client, water_requirement_level="high")

    response = client.post(
        "/api/v1/agri-assistant/ask",
        json={
            "question": "Why was this field selected?",
            "crop_id": crop["id"],
            "top_n": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_field_id"] == field_alpha["id"]
    assert payload["selected_field_name"] == "Field Alpha"
    assert payload["used_fallback"] is True
    assert payload["model"] is None
    assert payload["why_this_field"][0].startswith("Rank #1")
    assert any("Field Beta" in alternative for alternative in payload["alternatives"])
    assert "deterministic ranking data" in payload["answer"]


def test_agri_assistant_api_rejects_selected_field_outside_ranked_results(client, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    field_alpha = _create_field(client, "Field Alpha")
    field_beta = _create_field(client, "Field Beta")
    _create_soil_test(client, field_alpha["id"])
    _create_soil_test(client, field_beta["id"])
    crop = _create_crop(client)

    response = client.post(
        "/api/v1/agri-assistant/ask",
        json={
            "question": "Compare these fields.",
            "crop_id": crop["id"],
            "field_ids": [field_alpha["id"]],
            "selected_field_id": field_beta["id"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Selected field is not present in the ranked results"


def test_agri_assistant_api_returns_same_deterministic_sections_as_context_builder(client, db, monkeypatch):
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)

    field_alpha = _create_field(client, "Field Alpha")
    field_beta = _create_field(client, "Field Beta", irrigation_available=False, slope_percent=15.0)
    _create_soil_test(client, field_alpha["id"])
    _create_soil_test(client, field_beta["id"], ph=5.0, organic_matter_percent=1.0, depth_cm=50.0, ec=3.0)
    crop = _create_crop(client, water_requirement_level="high")

    ranking_response = get_ranked_fields_response(db, crop_id=crop["id"], top_n=2)
    context = build_agri_assistant_context(ranking_response)

    response = client.post(
        "/api/v1/agri-assistant/ask",
        json={
            "question": "What should I know about this choice?",
            "crop_id": crop["id"],
            "top_n": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["why_this_field"] == context.why_this_field
    assert payload["alternatives"] == context.alternatives
    assert payload["risks"] == context.risks
    assert payload["missing_data"] == context.missing_data
