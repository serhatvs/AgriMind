# AgriMind

AgriMind is an AI-powered agricultural decision support platform for ranking fields, matching crops to land, and generating explainable recommendations from agronomic data.

The current repository contains a FastAPI backend MVP with:

- field, crop, and soil test management APIs
- a rule-based suitability engine
- multi-field crop ranking
- explanation generation for each recommendation
- provider-based AI seams for swapping deterministic, ML, and LLM components
- sample seed data and automated tests

## Product Goal

The core MVP goal is simple:

> Rank a portfolio of fields and determine the best field for a selected crop.

From that foundation, AgriMind is intended to evolve into a broader agricultural intelligence platform that combines deterministic agronomic rules, machine learning, and natural-language AI.

## Current Backend Scope

Implemented today:

- `fields`: CRUD for field metadata such as area, slope, irrigation availability, and drainage quality
- `soil_tests`: soil chemistry and texture records per field
- `crops`: crop requirement profiles including pH, nutrient targets, water, drainage, slope, and minimum area requirements
- `rank-fields`: rank multiple fields for a selected crop
- `recommendation`: generate a scored recommendation and human-readable explanation for a field/crop pair
- `management-plan`: generate a structured weekly irrigation and fertilizer plan for an active field crop cycle
- `agri-assistant`: ask grounded natural-language questions over deterministic ranking and explanation results

Not implemented yet:

- risk prediction models
- economic optimization
- conversation memory or RAG integration
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

The backend now separates domain workflows from AI provider implementations:

- `app/api`: FastAPI route handlers
- `app/services`: data access and persistence logic
- `app/engines`: compatibility facades for existing suitability, ranking, and explanation imports
- `app/ai`: provider contracts, registries, orchestration, and concrete rule-based / ML / LLM providers
- `app/models`: SQLAlchemy models
- `app/schemas`: Pydantic request/response schemas
- `migrations`: Alembic migration support
- `tests`: API and engine tests

The provider layer keeps the business logic stable while allowing AI capabilities to be swapped:

- data layer: PostgreSQL + SQLAlchemy models
- knowledge layer: crop profiles and rule logic
- rule-based providers: suitability, risks, explanation, ranking augmentation, extraction
- ML providers: yield prediction
- LLM providers: grounded Q&A and future extraction/generation workflows
- orchestration layer: ranking, recommendation, yield, and assistant flows

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
YIELD_PROVIDER=xgboost
RISK_PROVIDER=rule_based
EXPLANATION_PROVIDER=rule_based
EXTRACTION_PROVIDER=rule_based
AI_SUITABILITY_PROVIDER=rule_based
AI_RANKING_AUGMENTATION_PROVIDER=rule_based
AI_ASSISTANT_PROVIDER=openai
YIELD_MODEL_DIR=artifacts/yield_model
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
```

For development or integration testing, the deterministic stub providers can be enabled explicitly:

```env
YIELD_PROVIDER=stub
RISK_PROVIDER=stub
EXPLANATION_PROVIDER=deterministic
EXTRACTION_PROVIDER=stub
```

The default configuration is defined in [`app/config.py`](/c:/Users/VICTUS/Workspace/AgriMind/app/config.py).

Short provider env vars are preferred for yield, explanation, risk, and extraction. Legacy `AI_*` names remain supported and are normalized through the same validation rules.

Supported values in the current build:

- `YIELD_PROVIDER`: `stub`, `ml`, or `xgboost`
- `EXPLANATION_PROVIDER`: `deterministic` or `rule_based`
- `RISK_PROVIDER`: `rule_based` or `stub`
- `EXTRACTION_PROVIDER`: `manual`, `rule_based`, or `stub`

Provider ids are validated during settings load and again on startup. Invalid or unknown provider ids fail fast before the API begins serving requests.

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
- `GET /api/v1/fields/{field_id}/management-plan`
- `POST /api/v1/rank-fields/`
- `GET /api/v1/recommendation/{field_id}/{crop_id}`
- `POST /api/v1/agri-assistant/ask`

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
