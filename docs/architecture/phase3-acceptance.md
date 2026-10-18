# Phase 3 Acceptance Record

Date: 2026-10-16

## First-Party Ingestion

- WordPress RSS source `28` imported 10 articles and then completed an incremental
  run with zero new records.
- YouTube source `29` imported 17 metadata-only outbound video references. Its
  next run created zero records and identified the publication-boundary item as
  unchanged.
- Both sources reported zero consecutive failures after the incremental run.
- No external video bytes, download URLs, local paths, or storage keys were stored.

## Enrichment And Recovery

- Structured classification and moderation completed through LiteLLM.
- A concurrent Qdrant collection-creation conflict was reproduced, fixed, and
  recovered by replaying content `58`.
- The recovered record stored a 1536-dimension embedding under the configured
  `standards-embedding` alias.
- Content `62` exercised the audited human approval path and became searchable
  after embedding creation.

## Search

- Hybrid search returned `semantic_available: true`.
- The query `school work tech career` ranked content `62` first through semantic
  matching and also returned the related YouTube video through keyword matching.
- The versioned relevance set is `apps/api/evals/phase3_search_eval.jsonl`.
- Retrieval evaluation reports Precision@K and mean reciprocal rank (MRR) using
  canonical URLs rather than environment-specific database identifiers.

## Stabilization Controls

- Publication chronology is calculated deterministically in UTC before model use.
- Prompt version `content-enrichment-v3` supplies evaluation time, publication
  status, and age; genuine future timestamps are forced to human review.
- False future-date-only model reviews are deterministically cleared for verified
  past or present timestamps without weakening unrelated safety concerns.
- Scheduler replay includes stale model, prompt, schema, and embedding versions,
  but excludes enrichments with a recorded human decision.
- Playwright covers Hybrid, Keyword, Semantic, empty, unavailable, and outbound
  publisher-link behavior on desktop and mobile Chromium projects.
