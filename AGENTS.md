# Edu DawnSynch Engineering Guide

## Product Boundary

Edu DawnSynch is a modular monolith for technology learning discovery. Keep the first version focused on content ingestion foundations, source governance, classification, recommendations, search, feeds, user preferences, bookmarks, progress, opt-in digest delivery, and administrative monitoring.

Do not implement later-phase capabilities until their phase is explicitly opened. Phase 1 is infrastructure and application foundation only.

## Architecture Rules

- Use a modular monolith. Keep domain modules in one API codebase and split runtime processes by command: `api`, `worker`, and `scheduler`.
- Route all model calls through LiteLLM. Application code must not call OpenAI or any provider SDK directly.
- Prefer deterministic validation before AI classification or moderation.
- Enforce source-specific rights, attribution, retention, and allowed usage before storing or surfacing content.
- Never download or rehost external videos. Store canonical metadata and outbound links only.
- Require explicit newsletter or digest consent before scheduling or sending email.
- Use environment variables for configuration. Do not hardcode secrets, API keys, tokens, credentials, or private URLs.
- Add migrations for database changes. Do not rely on ORM auto-create in production paths.
- Keep health checks cheap, deterministic, and dependency-aware.
- Add tests with meaningful assertions for new behavior.

## Repository Layout

- `apps/api`: FastAPI, Pydantic v2 settings, SQLAlchemy, Alembic, Celery.
- `apps/web`: Next.js, React, TypeScript, Tailwind CSS.
- `docs/architecture`: system design and implementation plan.
- `docs/decisions`: architecture decision records.
- `.github/workflows`: CI checks.

## Development Standards

- Keep modules small and typed. Favor explicit dependencies over globals.
- Use async SQLAlchemy in API request paths.
- Keep Celery tasks idempotent. Include retry strategy when a task calls an external service.
- Validate source permissions and content shape before AI enrichment.
- Log structured events with request, task, and source identifiers where available.
- Return stable JSON from API endpoints. Document response contracts with Pydantic models.
- Keep frontend data fetching behind small typed helpers in `src/lib`.
- Do not put provider keys in `.env.example`. Use placeholder names only.

## Test Expectations

- API: `pytest` for settings, routes, migrations, and domain services.
- Web: `npm run lint`, `npm run typecheck`, `npm test`, and Playwright when browser behavior is introduced.
- CI should run API and web checks independently.

## Local Commands

- Start stack: `docker compose up --build`
- Run API migrations: `docker compose run --rm api alembic upgrade head`
- API tests: `cd apps/api && pytest`
- Web checks: `cd apps/web && npm run lint && npm run typecheck && npm test`

