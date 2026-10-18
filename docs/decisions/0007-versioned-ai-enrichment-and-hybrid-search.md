# ADR 0007: Versioned AI Enrichment And Hybrid Search

## Status

Accepted.

## Context

Classification, moderation, quality assessment, embeddings, and search must be
repeatable, auditable, rights-aware, and independent of a specific model provider.
Model output and pricing metadata can vary while content and source policy change
over time.

## Decision

- Send all analysis and embedding requests through the OpenAI-compatible LiteLLM
  gateway. Application code does not call provider SDKs.
- Require strict JSON-schema output and validate it again with Pydantic before
  persistence.
- Store prompt, schema, model alias, input fingerprint, moderation, quality, and
  classification provenance in PostgreSQL.
- Store one usage event per attempted model operation. Token counts are always
  retained when returned; cost remains null when LiteLLM does not report it.
- Store vectors in an Edu-specific Qdrant collection and relational vector
  references in PostgreSQL.
- Enforce source approval, rights-review dates, retention, and embedding permission
  before model or vector operations.
- Exclude unmoderated and review-required content from public search.
- Fuse PostgreSQL full-text and Qdrant semantic ranks using weighted reciprocal rank
  fusion. Hybrid search falls back to keyword results when semantic infrastructure
  is unavailable.

## Consequences

The system can re-enrich content safely when input or model versions change, inspect
AI spend without embedding provider pricing in application code, and remain useful
during model-gateway outages. Search quality depends on configured LiteLLM aliases
and must be measured against the versioned evaluation dataset.
