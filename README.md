# AgriMind

AgriMind is an AI-powered agricultural decision support platform for ranking fields, matching crops to land, and generating explainable recommendations from agronomic data.

The current repository contains a FastAPI backend MVP with:

- field, crop, and soil test management APIs
- a rule-based suitability engine
- multi-field crop ranking
- explanation generation for each recommendation
- sample seed data and automated tests

## Product Goal

The core MVP goal is simple:

> Rank a portfolio of fields and determine the best field for a selected crop.

From that foundation, AgriMind is intended to evolve into a broader agricultural intelligence platform that combines deterministic agronomic rules, machine learning, and natural-language AI.

## Current Backend Scope

Implemented today:

- `fields`: CRUD for field metadata such as area, slope, irrigation availability, and drainage quality
- `soil_tests`: soil chemistry and texture records per field
- `crops`: crop requirement profiles including pH, nutrient, water, drainage, slope, and minimum area requirements
- `rank-fields`: rank multiple fields for a selected crop
- `recommendation`: generate a scored recommendation and human-readable explanation for a field/crop pair

Not implemented yet:

- yield prediction models
- risk prediction models
- economic optimization
- irrigation and fertilization planning
- LLM or RAG integration
- frontend dashboard

## How The MVP Makes Decisions

The current decision engine is rule-based and uses weighted scoring from [`config/scoring_weights.json`](/c:/Users/VICTUS/Workspace/AgriMind/config/scoring_weights.json):

- pH compatibility
- nitrogen availability
- phosphorus availability
- potassium availability
- drainage fit
- irrigation fit
- slope fit
- soil texture fit

In addition to weighted scoring, the engine now applies minimum field area as a blocking constraint so undersized fields are not recommended even if other agronomic conditions look strong.

## Architecture

The backend follows a straightforward layered structure:

- `app/api`: FastAPI route handlers
- `app/services`: data access and persistence logic
- `app/engines`: suitability, ranking, and explanation logic
- `app/models`: SQLAlchemy models
- `app/schemas`: Pydantic request/response schemas
- `migrations`: Alembic migration support
- `tests`: API and engine tests

This maps well to the target platform direction:

- data layer: PostgreSQL + SQLAlchemy models
- knowledge layer: crop profiles and rule logic
- rule engine: suitability scoring and hard constraints
- decision engine: ranking and recommendation generation
- future ML layer: yield, risk, and optimization models
- future LLM layer: explanation, Q&A, and RAG workflows

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure the database

Create a `.env` file or export `DATABASE_URL`.

Example:

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/agrimind
```

The default configuration is defined in [`app/config.py`](/c:/Users/VICTUS/Workspace/AgriMind/app/config.py).

### 3. Run the API

```bash
uvicorn app.main:app --reload
```

The API starts on `http://localhost:8000` and exposes routes under `http://localhost:8000/api/v1`.

### 4. Seed sample data

```bash
python seed.py
```

### 5. Run tests

```bash
pytest
```

## Key Endpoints

See full examples in [`docs/API.md`](/c:/Users/VICTUS/Workspace/AgriMind/docs/API.md).

- `POST /api/v1/fields/`
- `GET /api/v1/fields/`
- `POST /api/v1/soil-tests/`
- `GET /api/v1/soil-tests/field/{field_id}`
- `POST /api/v1/crops/`
- `POST /api/v1/rank-fields/`
- `GET /api/v1/recommendation/{field_id}/{crop_id}`

## Roadmap

### Phase 1. Agronomic scope definition

- define target crops and region
- standardize field and soil inputs
- build crop requirement profiles

### Phase 2. Data infrastructure

- production-grade PostgreSQL schema
- historical field records
- weather and economics datasets

### Phase 3. Knowledge and rules

- agronomic rule base
- fertilizer and irrigation guidelines
- stronger hard-constraint filtering

### Phase 4. Product MVP

- field ranking workflow
- explainable recommendation output
- dashboard UI

### Phase 5. Predictive intelligence

- yield prediction
- risk scoring
- economic outcome modeling

### Phase 6. AI assistant

- natural-language questions
- recommendation reasoning
- retrieval-augmented generation

### Phase 7. Enterprise expansion

- multi-region support
- sensor and satellite integrations
- continuous learning pipelines

## Disclaimer

AgriMind recommendations are advisory and should be validated with local agronomists and field experts before operational use.

## Philosophy

> We do not replace farmers. We augment their decisions with intelligence.
