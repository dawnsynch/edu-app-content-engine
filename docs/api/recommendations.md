# Phase 4 Recommendation API

## Privacy And Policy Boundary

Learner profiles use generated UUIDs and contain only career preferences, selected technology domains, and a skill level. Engagement events accept only `view`, `click`, `start`, or `complete` plus an optional bounded dwell duration. The API does not collect PII or arbitrary event metadata.

Recommendations include only validated, unexpired content from active sources whose rights status is `approved` or `restricted`. Enrichment must be completed and moderation-safe. Current source summary and thumbnail permissions are applied again when rendering the feed.

## Create A Learner

```bash
curl -sS -X POST http://localhost:8010/api/v1/learners \
  -H 'Content-Type: application/json' \
  -d '{
    "career_preferences": ["software developer"],
    "technology_domains": ["python", "web development"],
    "skill_level": "beginner"
  }' | jq
```

Store the returned UUID in the client. It is intentionally anonymous and is not an authentication credential.

## Read Or Update Preferences

```text
GET   /api/v1/learners/{learner_id}/preferences
PATCH /api/v1/learners/{learner_id}/preferences
```

Any update increments `recommendation_version` and invalidates the previous cached feed.

## Get Recommendations

```bash
curl -sS 'http://localhost:8010/api/v1/learners/{learner_id}/recommendations?limit=10' | jq
```

Each item includes source attribution, a score, and a component-level explanation. Follow `next_cursor` for stable pagination. A cursor becomes stale after preferences or signals change and returns HTTP 400.

Cold-start profiles with no career or domain selections receive quality-, freshness-, and level-led recommendations. The response exposes `cold_start` and whether diversity changed the raw score order.

## Signals

```text
PUT    /api/v1/learners/{learner_id}/bookmarks/{content_id}
DELETE /api/v1/learners/{learner_id}/bookmarks/{content_id}
GET    /api/v1/learners/{learner_id}/bookmarks
PUT    /api/v1/learners/{learner_id}/dismissals/{content_id}
DELETE /api/v1/learners/{learner_id}/dismissals/{content_id}
POST   /api/v1/learners/{learner_id}/engagement-events
```

Engagement example:

```json
{
  "content_id": 62,
  "event_type": "click",
  "dwell_seconds": 45
}
```

Bookmarks positively influence ranking. Dismissals exclude an item. Bookmarking an item clears its dismissal, and dismissing it clears its bookmark.

## Configuration

- `RECOMMENDATION_CACHE_TTL_SECONDS`, default `300`
- `RECOMMENDATION_CANDIDATE_LIMIT`, default `500`
