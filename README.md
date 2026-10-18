# Edu DawnSynch

AI-powered technology learning discovery and approved-content aggregation platform.

## Implemented Scope

This repository implements the production-oriented foundation through the
Phase 4 Recommendation Engine:

- Docker Compose with separate `web`, `api`, `worker`, and `scheduler` processes.
- FastAPI skeleton with live and readiness health endpoints.
- Existing PostgreSQL 16 with an isolated Edu database.
- Alembic migration structure.
- Existing Redis with isolated cache, broker, and result databases.
- Existing Qdrant with an Edu collection prefix.
- Existing LiteLLM gateway configuration.
- Next.js starter that connects to the API.
- API and web test/lint/type-check structure.
- Source rights, retention, attribution, approval, and connector configuration.
- RSS/Atom, owned CMS, official YouTube API, and manual course connectors.
- Incremental Celery ingestion, deduplication, retries, run history, and source health.
- Hourly batched retention enforcement and source-policy filtering before persistence.
- LiteLLM-backed structured classification, moderation, and quality assessment.
- Rights-aware Qdrant embeddings and PostgreSQL/Qdrant hybrid search.
- AI token, latency, request, and gateway-reported cost tracking.
- Versioned Phase 3 evaluation data and a moderation review queue.
- Anonymous career, technology-domain, and learner-level preferences.
- Explainable weighted recommendations with cold start, diversity, and pagination.
- Bookmark, dismissal, and constrained anonymous engagement signals.
- Permission-aware candidate selection and versioned Redis feed caching.

Learning progress, saved searches, and digests are intentionally not implemented yet.

## Requirements

- Docker Desktop for Apple Silicon Mac.
- Node.js 22 for local web development outside Docker.
- Python 3.12 for local API development outside Docker.

## Shared Infrastructure

By default, this project reuses the infrastructure already running on this development host. It does not define or start PostgreSQL, Redis, Qdrant, or LiteLLM containers.

The application containers join these external Docker networks:

- `enterprise-review-net`: aliases `redis` and `litellm`
- `ai-network`: container names `postgres` and `qdrant`

Isolation is logical even though the processes are shared:

- PostgreSQL database and role: `edu_dawnsynch`
- Redis cache: database `8`
- Celery broker: database `9`
- Celery results: database `10`
- Qdrant collection prefix: `edu_dawnsynch`

Do not point Edu DawnSynch at another application's PostgreSQL database, Redis databases, or Qdrant collections.

## One-Time Setup

Create the local environment file:

```bash
cp .env.example .env
```

Edit `.env` and set:

- A new password in both PostgreSQL URLs.
- The existing LiteLLM master key.
- A model alias already configured in the shared LiteLLM gateway.
- An embedding model alias already configured in the shared LiteLLM gateway.
- A long random `ADMIN_API_KEY` for administrative endpoints.
- An official `YOUTUBE_API_KEY` only when YouTube sources are enabled.

Create a dedicated role and database through the existing PostgreSQL container. First open `psql` using that container's configured administrator:

```bash
docker exec -it postgres sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Then execute, replacing the password with the same value used in `.env`:

```sql
CREATE ROLE edu_dawnsynch LOGIN PASSWORD 'replace_with_a_unique_password';
CREATE DATABASE edu_dawnsynch OWNER edu_dawnsynch;
```

The existing `postgres:16` image does not include `pgvector`. Edu DawnSynch therefore uses the existing Qdrant service for vectors and keeps PostgreSQL relational-only. See [ADR 0004](docs/decisions/0004-shared-infrastructure-and-qdrant.md).

## Run With Docker Compose

```bash
docker compose up --build
```

In another terminal, run migrations:

```bash
docker compose run --rm api alembic upgrade head
```

Open:

- Web: http://localhost:3000
- API live health: http://localhost:8010/health/live
- API readiness: http://localhost:8010/health/ready
- LiteLLM liveliness: http://localhost:4000/health/liveliness

The API uses host port `8010` because the existing application already owns `127.0.0.1:8000`.

## Verify LiteLLM Provider

Use the existing LiteLLM master key to check the shared gateway:

```bash
curl http://localhost:4000/v1/models \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY"
```

Choose one returned model alias for `LITELLM_MODEL`. Provider keys remain owned by the shared LiteLLM deployment; they are not duplicated in this repository. Application code must route AI requests through LiteLLM rather than calling provider SDKs directly.

## Phase 2 Administrative API

Phase 2 provides API-key protected source registry and normalized content endpoints:

- `POST/GET /api/v1/admin/sources`
- `GET/PATCH/DELETE /api/v1/admin/sources/{source_id}`
- `POST/GET /api/v1/admin/content`
- `GET /api/v1/admin/content/{content_id}`
- `POST/GET /api/v1/admin/courses`
- `POST /api/v1/admin/sources/{source_id}/ingest`
- `GET /api/v1/admin/sources/{source_id}/health`
- `GET /api/v1/admin/ingestion/runs`
- `GET /api/v1/admin/ingestion/runs/{run_id}`

Send the configured key as `X-Admin-Key`. Source deletion is a soft archive so policy history is retained. List endpoints use the `after_id` cursor and accept a maximum `limit` of 100.

Example source registration:

```bash
curl -X POST http://localhost:8010/api/v1/admin/sources \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: $ADMIN_API_KEY" \
  -d '{
    "name": "Example Learning",
    "slug": "example-learning",
    "source_type": "website",
    "base_url": "https://learn.example.com",
    "status": "active",
    "rights_status": "approved",
    "storage_mode": "metadata_only",
    "attribution_required": true,
    "attribution_text": "Example Learning",
    "allow_summaries": true,
    "allow_embeddings": true
  }'
```

External videos are metadata-only references. Video payloads containing binary data, download URLs, local paths, or storage keys are rejected deterministically.

See [Phase 2 Ingestion API](docs/api/ingestion.md) for connector contracts and
configuration. Run the PostgreSQL acceptance suite for incremental ingestion,
failure recovery, owned CMS, YouTube metadata-only storage, manual curation, and
retention enforcement with:

```bash
docker compose run --rm api \
  sh -c 'TEST_DATABASE_URL="$DATABASE_URL" python -m pytest -m integration -v'
```

## Phase 3 AI And Search

Apply the Phase 3 migration and rebuild the application processes:

```bash
docker compose run --rm api alembic upgrade head
docker compose up -d --build --force-recreate api worker scheduler web
```

Open http://localhost:3000 for hybrid learning-content search. Administrative AI
operations and cost totals are available under `/api/v1/admin/ai`; see
[Phase 3 AI And Search API](docs/api/ai-search.md) for contracts and configuration.

Evaluate live search relevance from the API container:

```bash
docker compose exec api \
  python -m app.modules.search.evaluate_cli --base-url http://localhost:8000 -k 5
```

## Phase 4 Recommendations

Apply the Phase 4 migration and rebuild the API:

```bash
docker compose run --rm api alembic upgrade head
docker compose up -d --build --force-recreate api
```

Create anonymous learner profiles, record signals, and retrieve explainable feeds through
`/api/v1/learners`. See [Phase 4 Recommendation API](docs/api/recommendations.md) for examples.

The web application opens on the learner workspace. A first-time learner selects career
directions, technology domains, and a current skill level; the generated anonymous learner UUID
is stored in versioned browser local storage. The `For you` view supports score explanations,
bookmarking, dismissing, preference editing, and cursor-based loading. The `Search` view retains
the Phase 3 hybrid discovery workflow. Temporary API failures preserve the local learner identity
and provide an explicit retry state.

## Local API Development

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install ".[dev]"
pytest
ruff check .
mypy app
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Run migrations against a configured database:

```bash
alembic upgrade head
```

## Local Web Development

```bash
cd apps/web
npm install
npm run dev
```

Checks:

```bash
npm run lint
npm run typecheck
npm test
npx playwright install chromium
npm run test:e2e
```

## Remote Deployment

GitHub Actions can build versioned API and web images in GHCR and deploy them to
the Linux development server after CI succeeds on `main`. Runtime secrets stay
in the server-side `.env` file. See
[GitHub Actions Development Deployment](docs/deployment/github-actions.md) for
server prerequisites, required GitHub environment secrets, first deployment,
and rollback behavior.

## Architecture Docs

- [Architecture](docs/architecture/architecture.md)
- [Implementation Plan](docs/architecture/implementation-plan.md)
- [ADR 0001: Modular Monolith](docs/decisions/0001-modular-monolith.md)
- [ADR 0002: LiteLLM AI Boundary](docs/decisions/0002-litellm-ai-boundary.md)
- [ADR 0003: Deterministic Validation Before AI](docs/decisions/0003-deterministic-validation-before-ai.md)
- [ADR 0004: Shared Infrastructure And Qdrant](docs/decisions/0004-shared-infrastructure-and-qdrant.md)
- [ADR 0005: Source Policy And Content Boundary](docs/decisions/0005-source-policy-and-content-boundary.md)
- [ADR 0006: Incremental Connector Boundary](docs/decisions/0006-incremental-connector-boundary.md)
- [ADR 0007: Versioned AI Enrichment And Hybrid Search](docs/decisions/0007-versioned-ai-enrichment-and-hybrid-search.md)
- [ADR 0008: Explainable Deterministic Recommendations](docs/decisions/0008-explainable-deterministic-recommendations.md)

