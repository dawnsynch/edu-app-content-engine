# Phase 3 AI And Search API

## Configuration

`LITELLM_MODEL` and `LITELLM_EMBEDDING_MODEL` must be aliases configured in the
shared LiteLLM gateway. `LITELLM_MASTER_KEY` authenticates gateway calls. Provider
keys remain outside Edu DawnSynch.

Optional controls:

- `AI_PROMPT_VERSION` and `AI_SCHEMA_VERSION` invalidate stale enrichments.
- `AI_MIN_CONFIDENCE` routes uncertain output to review.
- `AI_MAX_RETRIES` controls bounded Celery retries for transient failures.
- `ENRICHMENT_BATCH_SIZE` bounds each scheduled dispatch.
- `QDRANT_API_KEY` authenticates Qdrant when its API-key mode is enabled.

## Admin Endpoints

All admin endpoints require `X-Admin-Key`:

- `POST /api/v1/admin/ai/content/{content_id}/enrich`: queue enrichment.
- `GET /api/v1/admin/ai/content/{content_id}`: inspect current enrichment.
- `GET /api/v1/admin/ai/review-queue`: list uncertain or moderated items.
- `POST /api/v1/admin/ai/review-queue/{content_id}/decision`: record an audited
  approval or rejection. Approval creates an allowed embedding; rejection removes it.
- `GET /api/v1/admin/ai/usage`: inspect token, latency, request, and reported-cost totals.

The scheduler dispatches unenriched or changed content every minute. Tasks are
idempotent by content fingerprint and protected by per-content Redis locks. It
also replays stale model, prompt, schema, or embedding versions while preserving
records that already have an audited human decision.

Publication chronology is evaluated deterministically in UTC before calling the
model. The prompt receives the evaluation timestamp, authoritative publication
status, and publication age. A genuine future timestamp is always routed to
review unless the model has already made the stricter rejection decision.

## Search

`GET /api/v1/search?q=python&mode=hybrid&limit=20` is public and returns only active,
unexpired, successfully enriched, moderation-safe content. Modes are `keyword`,
`semantic`, and `hybrid`. Hybrid mode reports `semantic_available: false` when it
falls back to PostgreSQL keyword ranking.

## Evaluation

The classification dataset is `apps/api/evals/phase3_content_eval.jsonl`. It covers safe,
review, reject, beginner, intermediate, advanced, and ambiguous examples. The
deterministic evaluator measures required-topic recall, difficulty, moderation, and
quality-range agreement. Provider-backed evaluation runs should be performed before
changing a model alias, prompt version, or schema version.

The search relevance dataset is `apps/api/evals/phase3_search_eval.jsonl`. It uses
stable canonical URLs and the deterministic evaluator reports Precision@K,
reciprocal rank, and aggregate MRR. Run both evaluation test modules with:

```bash
pytest tests/test_ai_evaluation.py tests/test_search_evaluation.py
```

Run the relevance set against a live API and print per-query Precision@K plus
aggregate MRR with:

```bash
python -m app.modules.search.evaluate_cli --base-url http://localhost:8000 -k 5
```
