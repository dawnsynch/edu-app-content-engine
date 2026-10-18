# ADR 0004: Reuse Shared Infrastructure And Use Qdrant For Vectors

## Status

Accepted

## Context

The development host already runs PostgreSQL 16, Redis 7.4.1, Qdrant, and LiteLLM 1.90.2 for another modular application. Starting duplicate infrastructure wastes memory and creates host-port conflicts. The existing PostgreSQL image does not include the `pgvector` extension, while an operational Qdrant instance is already available.

## Decision

Edu DawnSynch reuses those infrastructure processes while isolating its data logically:

- PostgreSQL uses a dedicated `edu_dawnsynch` database and role.
- Redis uses database 8 for cache, 9 for the Celery broker, and 10 for results.
- Qdrant uses collection names prefixed with `edu_dawnsynch`.
- LiteLLM uses the existing gateway and one of its configured model aliases.
- Edu application containers join the existing external Docker networks; infrastructure containers remain owned by their original Compose project.

Qdrant is the vector store. PostgreSQL remains the relational source of truth and does not require `pgvector`.

## Consequences

- Edu DawnSynch does not create duplicate infrastructure containers.
- Infrastructure lifecycle remains independent from this repository.
- A failure or restart of shared infrastructure can affect both applications.
- Credentials, database names, Redis databases, Qdrant collection prefixes, and model aliases must remain application-specific.
- Deployment environments may provision equivalent managed services without changing application contracts.
