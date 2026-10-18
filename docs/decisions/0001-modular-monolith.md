# ADR 0001: Modular Monolith With Separate Runtime Processes

## Status

Accepted

## Context

Edu DawnSynch needs ingestion, enrichment, personalization, search, digest delivery, and administration. These domains are related and should evolve together during early product development.

## Decision

Use a modular monolith codebase with separate runtime processes for web, API, worker, and scheduler.

## Consequences

- Domain contracts stay simple and local.
- Deployment and local development remain approachable.
- Background work is operationally isolated through Celery processes.
- The team avoids premature microservice boundaries while preserving module ownership.

