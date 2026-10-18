import json
from decimal import Decimal

import httpx
import pytest

from app.core.settings import Settings
from app.modules.ai.client import LiteLLMClient
from app.modules.ai.schemas import EnrichmentDecision


def decision_payload() -> dict[str, object]:
    return {
        "topics": ["Python", "programming fundamentals"],
        "skills": ["Loops"],
        "career_paths": ["software developer"],
        "difficulty": "beginner",
        "quality": {
            "score": 0.8,
            "signals": {
                "completeness": 0.8,
                "clarity": 0.9,
                "authority": 0.7,
                "freshness": 0.8,
                "educational_value": 0.9,
            },
        },
        "moderation": {
            "status": "safe",
            "categories": [],
            "rationale": "Appropriate educational content.",
        },
        "confidence": 0.92,
    }


@pytest.mark.asyncio
async def test_litellm_client_uses_structured_output_and_tracks_cost() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url.path == "/v1/chat/completions"
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        assert "publication_date_status: past_or_present" in body["messages"][1]["content"]
        return httpx.Response(
            200,
            headers={"x-litellm-response-cost": "0.00042"},
            json={
                "id": "chat-request-1",
                "choices": [{"message": {"content": json.dumps(decision_payload())}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 40,
                    "total_tokens": 140,
                },
            },
        )

    settings = Settings(
        litellm_base_url="https://litellm.example.test",
        litellm_model="classification-alias",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await LiteLLMClient(client, settings).analyze(
            {
                "title": "Python loops",
                "content_type": "tutorial",
                "evaluated_at": "2026-10-16T07:00:00+00:00",
                "publication_date_status": "past_or_present",
                "publication_age_days": 1,
            }
        )

    assert result.decision.topics == ["python", "programming fundamentals"]
    assert result.usage.total_tokens == 140
    assert result.usage.cost_usd == Decimal("0.00042")


def test_structured_output_schema_forbids_extra_properties_recursively() -> None:
    schema = EnrichmentDecision.model_json_schema()

    assert schema["additionalProperties"] is False
    assert all(
        definition.get("additionalProperties") is False
        for definition in schema["$defs"].values()
        if definition.get("type") == "object"
    )


@pytest.mark.asyncio
async def test_litellm_embedding_uses_configured_alias() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"] == "embedding-alias"
        return httpx.Response(
            200,
            json={
                "id": "embedding-request-1",
                "data": [{"embedding": [0.1, 0.2, 0.3]}],
                "usage": {"prompt_tokens": 4, "total_tokens": 4},
            },
        )

    settings = Settings(
        litellm_base_url="https://litellm.example.test",
        litellm_embedding_model="embedding-alias",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await LiteLLMClient(client, settings).embed("search text")

    assert result.vector == [0.1, 0.2, 0.3]
    assert result.usage.input_tokens == 4
