import httpx
import pytest

from app.core.settings import Settings
from app.modules.ai.qdrant import QdrantVectorStore


@pytest.mark.asyncio
async def test_missing_collection_reports_semantic_search_unavailable() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(404))
    settings = Settings(qdrant_url="https://qdrant.example.test")

    async with httpx.AsyncClient(transport=transport) as client:
        result = await QdrantVectorStore(client, settings).search([0.1, 0.2], limit=10)

    assert result is None


@pytest.mark.asyncio
async def test_collection_creation_race_accepts_matching_existing_collection() -> None:
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.method)
        if requests == ["GET"]:
            return httpx.Response(404)
        if requests == ["GET", "PUT"]:
            return httpx.Response(409)
        return httpx.Response(
            200,
            json={"result": {"config": {"params": {"vectors": {"size": 2}}}}},
        )

    transport = httpx.MockTransport(handler)
    settings = Settings(qdrant_url="https://qdrant.example.test")

    async with httpx.AsyncClient(transport=transport) as client:
        await QdrantVectorStore(client, settings).ensure_collection(2)

    assert requests == ["GET", "PUT", "GET"]
