# ADR 0002: LiteLLM As The AI Provider Boundary

## Status

Accepted

## Context

The platform will need classification, quality assessment, moderation, summarization, embeddings, and recommendations. Provider choice and model aliases may change over time.

## Decision

Route all model requests through LiteLLM. Application code uses internal AI client abstractions pointed at the LiteLLM gateway and configured model aliases.

## Consequences

- Provider credentials stay outside application code.
- Model migration is a configuration concern where possible.
- Tests can mock a single gateway boundary.
- Direct provider SDK calls are prohibited in product modules.

