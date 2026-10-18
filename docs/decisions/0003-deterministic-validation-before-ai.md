# ADR 0003: Deterministic Validation Before AI Enrichment

## Status

Accepted

## Context

AI enrichment can be expensive and probabilistic. Content rights, retention, consent, and source approval are deterministic policy concerns.

## Decision

Validate source approval, content shape, retention, attribution, and newsletter consent before invoking AI workflows.

## Consequences

- Policy violations fail early and consistently.
- AI spend is reduced.
- Moderation and enrichment operate on cleaner inputs.
- Validation services become a required dependency of ingestion and digest workflows.

