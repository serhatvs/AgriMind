# AgriMind API Documentation

Base URL: `http://localhost:8000/api/v1`

## Fields

### POST /fields/
Create a new field.

**Request Body:**
```json
{
  "name": "North Valley Farm",
  "location_name": "North Valley",
  "latitude": 39.7817,
  "longitude": -89.6501,
  "area_hectares": 25.0,
  "slope_percent": 2.0,
  "irrigation_available": true,
  "water_source_type": "well",
  "infrastructure_score": 82,
  "drainage_quality": "excellent"
}
```

### GET /fields/
List all fields.

### GET /fields/{field_id}
Get a specific field by ID.

### GET /fields/{field_id}/management-plan
Get a structured weekly management plan for the field's active crop cycle.

**Query Parameters:**
- `target_date` (optional, `YYYY-MM-DD`)
- `weeks` (optional, default `8`, max `12`)

**Response Shape:**
```json
{
  "status": "ready",
  "field_id": 1,
  "crop_id": 2,
  "sowing_date": "2026-03-01",
  "target_date": "2026-03-08",
  "current_stage": "vegetative",
  "blockers": [],
  "weekly_plan": [
    {
      "week_index": 0,
      "start_date": "2026-03-08",
      "end_date": "2026-03-14",
      "stage_name": "vegetative",
      "irrigation": {
        "total_mm": 30.5,
        "frequency_per_week": 2,
        "mm_per_event": 15.25,
        "notes": [
          "Recent rainfall offsets 5.6 mm of weekly irrigation demand."
        ],
        "priority": "high"
      },
      "fertilizer_actions": [
        {
          "planned_date": "2026-03-08",
          "stage_name": "vegetative",
          "product": "NPK blend (15-15-15)",
          "priority": "high",
          "nutrient_gaps": [
            {
              "nutrient": "nitrogen",
              "current_ppm": 30.0,
              "target_ppm": 60.0,
              "deficit_ppm": 30.0,
              "severity": "high"
            }
          ],
          "notes": [
            "Immediate corrective application due to a high nutrient deficit."
          ]
        }
      ],
      "notes": []
    }
  ],
  "action_list": [
    {
      "action_type": "irrigation",
      "title": "Apply irrigation",
      "details": "Apply 30.5 mm across 2 events (15.25 mm/event).",
      "priority": "high",
      "week_index": 0,
      "planned_date": "2026-03-08",
      "start_date": "2026-03-08",
      "end_date": "2026-03-14",
      "stage_name": "vegetative",
      "product": null,
      "total_mm": 30.5,
      "frequency_per_week": 2
    }
  ]
}
```

### PUT /fields/{field_id}
Update a field.

### DELETE /fields/{field_id}
Delete a field.

## Soil Tests

### POST /soil-tests/
Create a new soil test.

**Request Body:**
```json
{
  "field_id": 1,
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
  "water_holding_capacity": 21.5
}
```

### GET /soil-tests/
List all soil tests.

### GET /soil-tests/field/{field_id}
Get all soil tests for a specific field.

## Crops

### POST /crops/
Create a new crop profile.

Optional nutrient target fields:
- `target_nitrogen_ppm`
- `target_phosphorus_ppm`
- `target_potassium_ppm`

### GET /crops/
List all crop profiles.

### GET /crops/{crop_id}
Get a specific crop by ID.

## Ranking

### POST /rank-fields/
Rank fields by suitability for a given crop.

**Request Body:**
```json
{
  "field_ids": [1, 2, 3],
  "crop_id": 1,
  "top_n": 5
}
```

**Response:**
```json
[
  {
    "rank": 1,
    "field_id": 1,
    "crop_id": 1,
    "score": 87.5,
    "explanation": "Field 'North Valley Farm' is highly suitable for Wheat (score: 87.5/100)..."
  }
]
```

## Recommendations

### GET /recommendation/{field_id}/{crop_id}
Get a suitability recommendation for a specific field and crop combination.

## Agri Assistant

### POST /agri-assistant/ask
Ask a natural-language question about deterministic ranking results. The ranking engine and explanation engine remain the source of truth; the LLM only phrases the answer.

**Request Body:**
```json
{
  "question": "Why was this field selected for corn?",
  "crop_id": 1,
  "field_ids": [1, 2, 3],
  "top_n": 3,
  "selected_field_id": 1
}
```

**Integration Example:**
1. Rank the fields for the crop:
```json
{
  "crop_id": 1,
  "field_ids": [1, 2, 3],
  "top_n": 3
}
```
2. Ask the assistant about one of the ranked fields:
```json
{
  "question": "Why this field instead of the others?",
  "crop_id": 1,
  "field_ids": [1, 2, 3],
  "top_n": 3,
  "selected_field_id": 1
}
```

**Response:**
```json
{
  "selected_field_id": 1,
  "selected_field_name": "North Valley Farm",
  "answer": "North Valley Farm ranked first because its agronomic fit is stronger and the current deterministic inputs show fewer constraints than the alternatives.",
  "why_this_field": [
    "Rank #1 with ranking score 88.4/100 and agronomic score 86.0/100.",
    "pH is within ideal range.",
    "Field has irrigation available."
  ],
  "alternatives": [
    "Rank #2 South Ridge (ranking score 75.0/100): strongest upside - Field has irrigation available. Relative score vs North Valley Farm: lower ranking score than North Valley Farm (75.0 vs 88.4). Main tradeoff - Field slope exceeds the crop tolerance."
  ],
  "risks": [
    "Drainage is below crop requirement."
  ],
  "missing_data": [
    "Estimated profit unavailable from current deterministic inputs."
  ],
  "used_fallback": false,
  "model": "gpt-4.1-mini-2025-04-14"
}
```
