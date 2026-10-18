# ADR 0006: Use Policy-Governed Incremental Connectors

## Status

Accepted

## Context

Approved providers expose different protocols, pagination, identifiers, and
failure behavior. Connector-specific code must not bypass source rights,
retention, attribution, deduplication, or the prohibition on rehosting external
video.

## Decision

Connectors return typed content candidates and an opaque next checkpoint. They
never write to the database. The ingestion service applies source policy and
persists candidates through the normalized content service. A checkpoint is
committed only after all accepted candidates have been persisted.

Phase 2 supports RSS/Atom over conditional HTTP, a documented first-party CMS
JSON contract, the official YouTube Data API, and manual course curation. It
does not provide a general web scraper. YouTube records contain metadata and
canonical outbound watch links only.

Celery dispatches due sources. Redis provides a bounded per-source lock. HTTP
transport errors, rate limits, and provider 5xx responses are transient and use
bounded exponential retries. Invalid payloads, missing credentials, unsupported
connectors, and policy violations are permanent failures.

## Consequences

- Provider credentials remain environment variables and never enter source JSON.
- Replaying a page is safe because provider IDs, canonical URLs, and fingerprints
  are deterministically deduplicated.
- A failed run records health information while preserving the last successful
  checkpoint.
- Adding a provider requires a connector implementation, fixtures, registry
  entry, and explicit source-policy review.
