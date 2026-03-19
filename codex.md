# Codex Operating Guide

## Purpose And Usage

This document is the repository-level operating guide for Codex working in AgriMind.

Codex must read and follow this file before making changes. Treat it as the default implementation standard for code, tests, naming, structure, and execution workflow in this repository.

When there is a conflict between speed, local convenience, and engineering quality, use this priority order:

1. Correctness
2. Maintainability
3. Consistency
4. Implementation speed

If the codebase already contains a reasonable pattern, follow it. If the local pattern is inconsistent or clearly harmful, standardize toward the best maintainable option with the smallest safe change.

## Core Engineering Principles

- Prefer simple, readable, maintainable solutions over clever ones.
- Minimize unnecessary abstractions. Add layers only when they clearly improve clarity, reuse, or safety.
- Keep files, functions, classes, and modules focused on one job.
- Avoid hidden side effects. Make state changes, database writes, and network calls obvious.
- Optimize for long-term maintainability, not quick patches that increase future cost.
- Preserve the existing architecture unless there is a strong, concrete reason to improve it.
- Avoid speculative overengineering for features the repository does not need yet.
- When changing existing code, align with surrounding patterns unless those patterns are clearly harmful.
- Prefer explicit control flow and data flow over magic behavior.
- Finish clean end-to-end slices instead of leaving partial implementations.

## Repository Shape

AgriMind currently follows a layered backend structure. Keep these boundaries clear:

- `app/api`: FastAPI route handlers and HTTP translation only.
- `app/services`: data access and persistence logic.
- `app/engines`: scoring, ranking, explanation, and other business or decision logic.
- `app/models`: SQLAlchemy ORM models.
- `app/schemas`: Pydantic request and response models.
- `config`: static configuration files such as scoring weights.
- `migrations`: Alembic migration history and migration wiring.
- `tests`: pytest test coverage for APIs and business logic.

Do not move logic across layers casually. In general:

- Routes should parse requests, call the right service or engine, and map domain errors to HTTP responses.
- Services should handle database reads and writes and return domain objects or explicit not-found results.
- Engines should contain deterministic business logic and avoid HTTP concerns.
- Schemas should define I/O contracts, not business workflows.

## Naming Conventions

Use descriptive names. Favor clarity over brevity.

### General Rules

- Use full words unless the abbreviation is universally standard, such as `id`, `api`, `db`, or `url`.
- Keep singular and plural usage accurate. A single object should not use a plural name, and collections should not use singular names.
- Boolean names must read like true or false statements, such as `irrigation_available`, `is_active`, or `has_errors`.
- Avoid misleading names that imply behavior the code does not actually have.
- Avoid one-letter names except trivial loop counters in short local scopes.

### Python Names

- Variables: `snake_case`, descriptive, scoped to the smallest useful context.
- Functions: `snake_case` verb phrases that state the action, such as `create_field`, `get_latest_soil_test_for_field`, or `generate_explanation`.
- Methods: same as functions; the name should describe the side effect or returned value.
- Classes: `PascalCase` nouns, such as `Field`, `FieldCreate`, `RankingResult`.
- Interfaces or protocols: `PascalCase` and suffix with `Protocol` or `ABC` when used.
- Type aliases: `PascalCase` noun phrases.
- Constants: `UPPER_SNAKE_CASE` for module-level values that are effectively constant.
- Enums: singular `PascalCase` enum names, uppercase members.

### Schema, Service, And Engine Naming

- Pydantic schema classes should keep the current pattern: `ResourceCreate`, `ResourceUpdate`, `ResourceRead`, `ResourceRequest`, `ResourceResult`.
- Service modules should use `<resource>_service.py`.
- Engine modules should use `<purpose>_engine.py`.
- Functions that fetch one record should use singular names such as `get_field`.
- Functions that fetch many records should use plural names such as `get_fields`.
- Ranking or scoring result containers should use suffixes such as `Result`, `Entry`, or `Score` when that improves clarity.

### Files And Folders

- File names: `snake_case.py`.
- Folder names: lowercase and descriptive; use plural resource folders or established architectural layer names.
- Do not create generic files like `utils.py`, `helpers.py`, or `misc.py` unless the contents are genuinely cohesive and broadly shared.

### Database Fields

- Use `snake_case`.
- Use explicit unit suffixes where relevant, such as `_hectares`, `_percent`, or `_ppm`.
- Use `_id` for foreign keys.
- Use `_at` for timestamps.
- Boolean columns should read like true or false statements.
- Keep agronomic terms precise and consistent across models, schemas, and API payloads.

### API Routes

- Keep routes versioned under `/api/v1` unless the project explicitly introduces a new versioning scheme.
- Use plural resource nouns for CRUD collections, such as `/fields`, `/soil-tests`, `/crops`.
- Use kebab-case in path segments when a multi-word route is needed, such as `/rank-fields`.
- Use path parameters with explicit resource names, such as `{field_id}` and `{crop_id}`.
- Avoid inventing action-heavy routes when standard resource modeling is sufficient.

## Code Style Rules

- Follow existing repository formatting unless and until a formatter is formally introduced.
- Use 4-space indentation and keep whitespace disciplined.
- Organize imports in this order: standard library, third-party packages, local application imports.
- Remove unused imports, dead locals, and commented-out code.
- Prefer early returns and guard clauses over deep nesting.
- Keep nesting shallow. If logic is heading past roughly three levels of indentation, simplify it.
- Prefer explicit intermediate variables when they make scoring or business rules easier to read and debug.
- Avoid duplicated logic. Extract a helper only when it improves clarity or removes meaningful repetition.
- Keep route handlers thin. They should mainly validate, orchestrate, and translate errors.
- Keep business functions focused. If a function is doing validation, querying, transformation, and formatting all at once, split it.
- As a rule of thumb, prefer functions under about 30 lines for routes and under about 50 lines for non-trivial business logic. Break them up when readability drops.
- Keep classes compact and cohesive. If a class grows beyond one clear responsibility or becomes difficult to scan, split it.
- Prefer explicit arguments and return values over mutating shared state.
- Write code that is easy to step through in a debugger and easy to reason about from logs and tests.

## Comments And Documentation

- Comments should explain why, not restate obvious code.
- Add comments for non-obvious business rules, edge cases, units, blocking constraints, or tradeoffs.
- Avoid noisy comments that narrate every line.
- Use short docstrings for public modules and functions when behavior is not immediately obvious from the signature.
- Keep comments and docs updated when behavior changes.
- When API behavior or payloads change, update the relevant documentation in `README.md`, `docs/API.md`, or both.

## Error Handling And Reliability

- Fail clearly, not silently.
- Do not swallow exceptions unless the decision is intentional, safe, and documented.
- Validate inputs at boundaries: request schemas, config parsing, database entry points, and external integrations.
- Handle edge cases explicitly, especially missing records, empty inputs, blocking constraints, and invalid state transitions.
- Use consistent error handling by layer.
- API layer: convert expected domain errors into appropriate `HTTPException` responses.
- Service and engine layers: return explicit not-found results or raise clear exceptions; do not mix patterns arbitrarily within the same area.
- Prefer actionable error messages that help a maintainer diagnose the issue quickly.
- Log useful debugging context without leaking secrets, credentials, tokens, or sensitive farm data.
- Avoid broad `except Exception` blocks. If one is necessary, narrow it as quickly as possible and explain why it exists.

## Testing Expectations

- Write or update tests for meaningful logic changes.
- Prefer targeted tests over large amounts of boilerplate.
- Cover normal flow, edge cases, and failure paths.
- Do not modify tests only to make broken behavior pass.
- Add API tests for route behavior and contract changes.
- Add focused business-logic tests for scoring, ranking, explanation generation, and constraint handling.
- Preserve testability even when no test exists yet. Small pure functions and clear boundaries are easier to test later.
- Keep tests readable and intention-revealing. Use fixtures when they reduce duplication without hiding setup meaningfully.
- If behavior changes intentionally, update both the implementation and the tests in the same change.

## Refactoring Behavior

- Make small opportunistic refactors when touching messy code if the cleanup is low risk and directly improves the area you are changing.
- Separate cleanup from logic changes when possible so diffs remain easy to review.
- Preserve behavior unless an intentional behavior change is part of the task.
- Rename variables, functions, or types when clarity materially improves.
- Do not introduce broad architectural churn without a concrete justification tied to current repository needs.
- Do not rewrite stable modules just to align with a preferred style.

## Performance And Speed Guidance

- Optimize developer speed by keeping code predictable, consistent, and low-ambiguity.
- Reuse existing services, schemas, and utilities when they fit cleanly.
- Avoid premature micro-optimizations.
- Pay attention to real bottlenecks in loops, database queries, repeated record lookups, rendering work, network calls, and large data handling.
- Prefer simple performance wins with low maintenance cost.
- When performance work is needed, fix the dominant cost first and keep the design understandable.
- Plan briefly, then execute decisively. Do not spend excessive time inventing abstractions before a working slice exists.

## File And Project Organization

- Keep related logic close together and in the correct layer.
- Avoid dumping unrelated utilities into generic shared modules.
- Prefer clear module boundaries over large mixed-purpose files.
- Create new files only when they improve clarity, reuse, ownership, or testability.
- Keep directory structure understandable from the top level.
- Match the existing domain split: fields, soil tests, crops, ranking, recommendations.
- Keep database migrations focused and reversible where practical.

## Git And Change Hygiene

- Make focused changes tied to the task.
- Avoid unrelated edits.
- Preserve clean diffs and stable public interfaces unless an interface change is intentional.
- Do not reformat entire files unless necessary for the change or unless repository tooling formalizes that behavior.
- Propagate intentional interface changes safely across routes, schemas, services, engines, tests, and docs.
- Prefer small reviewable commits when working in multiple steps.

## Security And Safety

- Never hardcode secrets.
- Never log tokens, passwords, API keys, connection strings, or private keys.
- Validate and sanitize external input at system boundaries.
- Use least-privilege thinking for database access and external integrations.
- Treat authentication, authorization, and data deletion logic as high-risk areas.
- Be careful with any code that affects recommendation trust, agronomic safety, or irreversible data changes.

## Decision Rules For Codex

- Inspect surrounding code before inventing a new pattern.
- Match the repository's real conventions when they are reasonable.
- If conventions are inconsistent, standardize toward the best local pattern and mention the decision in the change summary.
- Before large edits, make a short internal plan.
- Prefer finishing one clean end-to-end slice over leaving multiple half-done pieces.
- Do not leave placeholders, stubs, or TODO implementations unless the task explicitly asks for them.
- When uncertain, choose the more readable and maintainable option.
- When multiple valid solutions exist, prefer the one with lower complexity and lower future maintenance cost.
- Keep route, service, engine, model, and schema responsibilities distinct.
- Do not introduce a new dependency, cross-layer shortcut, or architectural pattern without a concrete need.

## Output Style For Codex

When reporting work back to the user:

- Briefly summarize what changed.
- Mention assumptions only when they affected the implementation.
- Mention follow-up risks or TODOs only when they are truly necessary.
- Keep explanations concise, technical, and focused on engineering impact.

## Project-Specific Placeholders

- Stack/language:
  Current: Python backend using FastAPI, SQLAlchemy 2.x, Pydantic 2.x, Alembic, and pytest.
  Placeholder: confirm the supported Python version and deployment/runtime targets.
- Architecture notes:
  Current: layered structure with `app/api`, `app/services`, `app/engines`, `app/models`, `app/schemas`, `config`, `migrations`, and `tests`.
  Placeholder: add module ownership rules, cross-module dependency limits, or future frontend/service boundaries if they become formal.
- Lint/formatter tools:
  Placeholder: no repository-level lint or formatter configuration was found. Add the exact required commands and standards when tooling is introduced.
- Test commands:
  Current: `pytest`
  Placeholder: add focused suite commands, coverage thresholds, or CI entry points if they are later standardized.
- Run commands:
  Current: `uvicorn app.main:app --reload`
  Current: `python seed.py`
  Placeholder: add local dev, Docker, or production run commands if those workflows are added.
- Build commands:
  Placeholder: no formal build or packaging command is defined in the repository yet.
- Domain-specific naming rules:
  Current: use explicit agronomic units and terms such as `area_hectares`, `slope_percent`, `nitrogen_ppm`, `ph_level`, and `drainage_quality`.
  Placeholder: document approved vocabularies for crop types, drainage labels, soil textures, ranking states, and recommendation labels.
- Forbidden patterns specific to this repo:
  Placeholder: formalize repo-specific anti-patterns if needed. Recommended candidates include silent exception swallowing, business logic inside route handlers, generic catch-all utility modules, and schema-model drift.
