# ADR 0005: Enforce Source Policy Before Content Persistence

## Status

Accepted

## Context

Edu DawnSynch can only aggregate content under source-specific usage rights.
Later ingestion and AI phases must not be able to bypass attribution, retention,
storage, domain, or transformation restrictions. External video media must not
be downloaded or rehosted.

## Decision

The `sources` table is the authoritative policy registry. Content persistence is
allowed only when a source is active and its rights status is approved or
restricted. The application validates canonical URL ownership, storage mode,
retention, attribution, and allowed transformations before inserting content.
Database constraints preserve core invariants if application validation is
bypassed.

The `content_items` table stores normalized metadata and outbound URLs. It does
not contain external video binaries, local media paths, download URLs, or object
storage keys. Canonical URLs, source-scoped provider IDs, and optional SHA-256
fingerprints provide deterministic deduplication before future AI processing.

## Consequences

- Ingestion adapters must use the source and content services instead of writing
  directly to the database.
- Sources remain in draft until rights review is complete.
- Source deletion is archival so policy history and content provenance remain
  available.
- Retention expiry is computed when content is accepted and can be enforced by a
  later scheduled cleanup task.
- A future change to source rights must trigger an explicit content-policy review;
  Phase 2 does not retroactively rewrite existing content.
