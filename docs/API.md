# AgriMind API Documentation

Base URL: `http://localhost:8000/api/v1`

## Fields

### POST /fields/
Create a new field.

**Request Body:**
```json
{
  "name": "North Valley Farm",
  "location": "North Valley",
  "area_hectares": 25.0,
  "slope_percent": 2.0,
  "irrigation_available": true,
  "drainage_quality": "excellent"
}
```

### GET /fields/
List all fields.

### GET /fields/{field_id}
Get a specific field by ID.

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
  "ph_level": 6.5,
  "nitrogen_ppm": 45.0,
  "phosphorus_ppm": 30.0,
  "potassium_ppm": 200.0,
  "organic_matter_percent": 3.5,
  "soil_texture": "loamy"
}
```

### GET /soil-tests/
List all soil tests.

### GET /soil-tests/field/{field_id}
Get all soil tests for a specific field.

## Crops

### POST /crops/
Create a new crop profile.

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
