# Implementation Plan

## Phase 1: Foundation

Scope:

- Docker Compose for Apple Silicon local development.
- FastAPI app skeleton with health endpoints.
- Shared PostgreSQL 16 for relational data and shared Qdrant for vectors.
- Alembic migrations.
- Redis.
- Celery worker and scheduler process skeletons.
- LiteLLM gateway configuration.
- Next.js starter that verifies API connectivity.
- CI, lint, type-check, and test structure.
- Reproducible setup documentation.

Exit criteria:

- `docker compose up --build` starts the stack.
- `alembic upgrade head` succeeds against the dedicated Edu database.
- API health endpoints return expected JSON.
- Frontend renders API health status.
- API tests and web checks pass.

## Phase 2: Dynamic Content Aggregation Engine

Status: implemented.

- Admin API-key protected source registry CRUD with soft archival.
- Source rights, retention, attribution, fetch cadence, allowed-domain, and transformation policy.
- Normalized content schema with canonical URL, external ID, and fingerprint deduplication.
- Deterministic URL, source approval, content type, retention, and external-video validation.
- Keyset pagination and PostgreSQL indexes aligned with list and retention queries.
- Typed connector interface and registry.
- RSS/Atom, owned CMS JSON API, official YouTube Data API, and manual course connectors.
- Durable ingestion runs, incremental checkpoints, ETag/Last-Modified support, and source health.
- Celery scheduling, per-source Redis locks, bounded exponential retries, and failure recovery.
- Hourly, batched deletion of content whose source retention deadline has expired.
- Mock-provider unit tests and PostgreSQL incremental-ingestion integration tests.

Exit criteria:

- Initial, unchanged, incremental, failed, and recovered ingestion runs are demonstrated.
- Failed runs preserve the last successful checkpoint.
- Restricted or unapproved sources cannot be queued or persisted.
- External videos remain metadata-only outbound references.

## Phase 3: AI Enrichment

Status: implemented.

- LiteLLM-only client boundary with strict structured output validation.
- Versioned classification, moderation, quality assessment, and Qdrant embeddings.
- Model alias, prompt version, schema version, fingerprint, and usage provenance.
- Token, latency, provider request ID, and gateway-reported cost tracking.
- Human review queue for low-confidence or policy-sensitive items.
- PostgreSQL keyword, Qdrant semantic, and reciprocal-rank hybrid search.
- Checked-in evaluation dataset and deterministic scoring utilities.
- Deterministic UTC publication-date policy and timestamp-aware prompt context.
- Canonical-URL search relevance cases with Precision@K and MRR metrics.
- Desktop and mobile Playwright acceptance coverage for learner search.

Exit criteria:

- Replaying unchanged enrichment does not repeat model calls.
- Restricted embedding policy prevents vector persistence.
- Review or rejected output is excluded from public search.
- Hybrid search falls back to keyword search when semantic dependencies fail.
- Retention removes both Qdrant vectors and PostgreSQL content.
- Usage totals distinguish reported cost from events where cost is unavailable.
- Stale prompt replay preserves completed human review decisions.

## Phase 4: Discovery And Personalization

Status: recommendation engine implemented.

- Anonymous learner profiles with career preferences, technology domains, and skill level.
- Explainable deterministic feed ranking using relevance, level fit, quality, freshness, and interactions.
- Bookmark, dismissal, and constrained anonymous engagement signals.
- Source-policy-aware candidate selection, diversity, cold start, cursor pagination, and Redis caching.
- Version-based cache invalidation on every preference or interaction mutation.
- Learner onboarding, personalized feed, explanation, bookmark, dismissal, and preference UI.
- Versioned browser persistence with desktop and mobile Playwright acceptance coverage.

Learning progress, expanded course directory filtering, and saved searches remain separately scoped discovery workflows.

## Phase 5: Digest And Admin Monitoring

- Add explicit digest consent and preferences.
- Add weekly digest scheduler and delivery audit.
- Add admin dashboards for source status, ingestion runs, moderation, and quality metrics.

