# Edu DawnSynch Architecture

## Context

Edu DawnSynch is an AI-powered technology learning discovery platform for students, graduates, career changers, and early-career professionals. It aggregates approved learning content, validates source permissions, enriches content with AI-assisted metadata, and personalizes discovery through feeds, course directories, semantic search, recommendations, bookmarks, progress tracking, and opt-in digests.

## System Shape

The platform is a modular monolith with separate runtime processes:

- `web`: Next.js user and admin interface.
- `api`: FastAPI HTTP API for product workflows and internal service boundaries.
- `worker`: Celery worker for ingestion, enrichment, moderation, recommendations, and digest jobs.
- `scheduler`: Celery Beat process for recurring ingestion and digest scheduling.
- `postgres`: shared PostgreSQL 16 server with an Edu-specific database for relational data.
- `redis`: Celery broker/result backend and short-lived cache.
- `qdrant`: vector storage for embeddings and semantic retrieval.
- `litellm`: shared gateway for all model provider calls.

The codebase remains one deployable product with clear modules rather than microservices. Runtime separation gives operational isolation without distributed domain ownership.

## Backend Modules

Planned API modules:

- `sources`: approved source registry, rights, retention, attribution, fetch policy, robots and terms metadata.
- `content`: normalized content item model, canonical URLs, metadata, tags, provider references.
- `ingestion`: deterministic fetch orchestration, source adapters, deduplication, retention enforcement.
- `ai`: LiteLLM client boundary, classification, quality scoring, moderation, embedding creation.
- `search`: semantic search, keyword filters, faceting, ranking.
- `recommendations`: user interest matching, freshness, diversity, and cold-start ranking.
- `learning`: feeds, course directory, bookmarks, and progress.
- `digest`: explicit opt-in consent, digest preferences, weekly schedule, delivery audit.
- `admin`: source management, job monitoring, moderation review.

Phase 1 implements the shared infrastructure and health surface. Phase 2 adds
source governance, normalized content, approved connectors, incremental Celery
ingestion, and source health. Phase 3 adds versioned AI enrichment, Qdrant
embeddings, cost telemetry, moderation gates, and hybrid search. Phase 4 adds
anonymous learner preferences and an explainable deterministic recommendation
engine with policy-aware candidates and versioned Redis caching.

## Data Architecture

PostgreSQL is the relational source of truth. Qdrant stores embeddings and supports semantic retrieval when AI enrichment is introduced. SQLAlchemy models and Alembic migrations are the required path for relational schema changes.

Foundation tables:

- `health_probe`: migration smoke table that proves database connectivity and migration execution.
- `sources`: approved-source registry and enforceable rights, attribution, retention, fetch, and transformation policy.
- `content_items`: normalized external-content metadata with source ownership, canonical URLs, retention expiry, and deduplication identifiers.
- `ingestion_runs`: immutable operational history and per-run content counters.
- `source_sync_states`: successful checkpoint, conditional HTTP state, schedule, and health counters.
- `content_enrichments`: versioned classification, moderation, quality, and vector provenance.
- `ai_usage_events`: per-operation tokens, latency, request ID, status, and gateway-reported cost.
- `learner_profiles`: anonymous preferences, skill level, and recommendation cache version.
- `learner_content_signals`: learner bookmarks and dismissals.
- `engagement_events`: constrained anonymous view, click, start, and completion events.

The relational schema uses bigint identity keys, time-zone-aware timestamps,
database constraints for policy invariants, indexed foreign keys, and keyset
pagination. Canonical URLs are globally unique; provider external IDs are unique
within a source; optional content fingerprints support cross-source duplicate
detection. Future tables should separate enrichment results, user preference
data, and delivery audit data. Qdrant points must use an Edu-specific collection
prefix and carry explicit model/version metadata so embeddings can be reprocessed
safely.

## AI Boundary

All model requests go through LiteLLM. The API should call an internal AI client that targets `LITELLM_BASE_URL` and uses model aliases from configuration. Provider-specific keys live only in environment variables consumed by LiteLLM.

Deterministic validation must happen before AI:

- source approval and usage rights
- URL normalization and deduplication
- required fields and content type checks
- retention and attribution policy checks
- newsletter consent checks

## Content Rights And Retention

The platform stores metadata, summaries, classifications, links, and source attribution. It must not download or rehost external videos. Source adapters must declare allowed usage, retention period, attribution text, and whether summaries, snippets, embeddings, or thumbnails are allowed.

## Observability

Phase 1 includes health endpoints and container health checks. Phase 2 adds
durable ingestion runs, source-level success/failure counters, latency, last
error, and next-due scheduling. Phase 3 adds model usage and cost events plus a
moderation review queue. Later phases should add exported metrics and alerting hooks.

## Security And Privacy

Configuration is environment-driven. Secrets are never committed. Phase 2
administrative endpoints require the `X-Admin-Key` header and fail closed when
`ADMIN_API_KEY` is absent. This shared-key mechanism is suitable for the initial
internal administration surface; user-scoped authentication and authorization
must replace it before exposing administration publicly. User digest consent
must be explicit, revocable, and audited.

