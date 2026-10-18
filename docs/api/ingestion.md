# Phase 2 Ingestion API

All endpoints require `X-Admin-Key`. Interactive contracts are available from
`/docs` and `/openapi.json`.

## Sources

- `POST /api/v1/admin/sources`: register policy and non-secret connector config.
- `GET /api/v1/admin/sources`: list sources with keyset pagination.
- `GET/PATCH/DELETE /api/v1/admin/sources/{source_id}`: inspect, update, or archive.
- `POST /api/v1/admin/sources/{source_id}/ingest`: queue an approved source.
- `GET /api/v1/admin/sources/{source_id}/health`: inspect checkpoint and health.

Connector configurations:

```json
{"source_type":"rss","connector_config":{"content_type":"article"}}
{"source_type":"owned_cms","connector_config":{"credential_env_var":"ACADEMY_API_TOKEN"}}
{"source_type":"youtube","connector_config":{"channel_id":"UC...","max_pages":5}}
```

Actual credentials must be supplied through environment variables. The owned
CMS contract is an HTTP `GET` returning:

```json
{"items":[{"external_id":"1","canonical_url":"https://example.com/1","title":"Course","content_type":"course"}],"next_cursor":"page-2"}
```

## Runs And Courses

- `GET /api/v1/admin/ingestion/runs`: filter with `source_id` or `status`.
- `GET /api/v1/admin/ingestion/runs/{run_id}`: run counters and failure details.
- `POST/GET /api/v1/admin/courses`: manually curate and list courses.

Statuses are `queued`, `running`, `succeeded`, `failed`, or `skipped`. Provider rate
limits, server errors, and transport failures are retried by Celery. Permanent
payload or policy failures are recorded without retry.

## Policy Enforcement

Description and thumbnail metadata are removed before persistence when the source
policy does not allow those transformations. This applies equally to automated
connectors and manually curated courses. Retention deadlines are enforced by the
hourly `retention.purge_expired_content` task, which deletes expired content in
bounded batches.
