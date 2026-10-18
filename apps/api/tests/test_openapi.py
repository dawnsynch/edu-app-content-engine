from fastapi.testclient import TestClient

from app.main import app


def test_phase_two_routes_are_documented() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]

    assert "/api/v1/admin/sources/{source_id}/ingest" in paths
    assert "/api/v1/admin/sources/{source_id}/health" in paths
    assert "/api/v1/admin/ingestion/runs" in paths
    assert "/api/v1/admin/courses" in paths
    assert "/api/v1/admin/ai/content/{content_id}/enrich" in paths
    assert "/api/v1/admin/ai/review-queue" in paths
    assert "/api/v1/admin/ai/review-queue/{content_id}/decision" in paths
    assert "/api/v1/admin/ai/usage" in paths
    assert "/api/v1/search" in paths
    assert "/api/v1/learners" in paths
    assert "/api/v1/learners/{learner_id}/preferences" in paths
    assert "/api/v1/learners/{learner_id}/recommendations" in paths
    assert "/api/v1/learners/{learner_id}/bookmarks/{content_id}" in paths
    assert "/api/v1/learners/{learner_id}/dismissals/{content_id}" in paths
    assert "/api/v1/learners/{learner_id}/engagement-events" in paths
