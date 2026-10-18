import json
from pathlib import Path

import httpx
import pytest
from pydantic import SecretStr

from app.modules.content.enums import ContentType
from app.modules.ingestion.connectors.base import ConnectorContext
from app.modules.ingestion.connectors.cms import OwnedCmsConnector
from app.modules.ingestion.connectors.errors import (
    PermanentConnectorError,
    TransientConnectorError,
)
from app.modules.ingestion.connectors.rss import RssAtomConnector
from app.modules.ingestion.connectors.youtube import YouTubeConnector

FIXTURES = Path(__file__).parent / "fixtures" / "providers"


def context(**overrides: object) -> ConnectorContext:
    values: dict[str, object] = {
        "source_id": 1,
        "base_url": "https://feeds.example.test/rss.xml",
        "connector_config": {},
        "checkpoint": {},
    }
    values.update(overrides)
    return ConnectorContext.model_validate(values)


@pytest.mark.asyncio
async def test_rss_connector_supports_incremental_ingestion() -> None:
    bodies = [
        (FIXTURES / "rss_initial.xml").read_bytes(),
        (FIXTURES / "rss_incremental.xml").read_bytes(),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=bodies.pop(0), headers={"ETag": '"feed-v1"'})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        connector = RssAtomConnector(client)
        initial = await connector.fetch(context())
        incremental = await connector.fetch(
            context(checkpoint=initial.checkpoint, etag=initial.etag)
        )

    assert [item.external_id for item in initial.items] == ["lesson-2", "lesson-1"]
    assert [item.external_id for item in incremental.items] == ["lesson-3"]
    assert incremental.etag == '"feed-v1"'


@pytest.mark.asyncio
async def test_atom_connector_parses_standard_alternate_link() -> None:
    body = (FIXTURES / "atom_initial.xml").read_bytes()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=body))

    async with httpx.AsyncClient(transport=transport) as client:
        result = await RssAtomConnector(client).fetch(context())

    assert len(result.items) == 1
    assert str(result.items[0].canonical_url) == "https://learn.example.test/atom-lesson-1"


@pytest.mark.asyncio
async def test_rss_connector_follows_same_domain_redirect() -> None:
    body = (FIXTURES / "rss_initial.xml").read_bytes()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/rss.xml":
            return httpx.Response(301, headers={"Location": "/static/feed.xml"})
        return httpx.Response(200, content=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await RssAtomConnector(client).fetch(context())

    assert len(result.items) == 2


@pytest.mark.asyncio
async def test_rss_failure_recovery_preserves_checkpoint() -> None:
    checkpoint = {"seen_ids": ["lesson-3", "lesson-2", "lesson-1"]}
    responses = [
        httpx.Response(503),
        httpx.Response(200, content=(FIXTURES / "rss_recovery.xml").read_bytes()),
    ]
    transport = httpx.MockTransport(lambda request: responses.pop(0))

    async with httpx.AsyncClient(transport=transport) as client:
        connector = RssAtomConnector(client)
        with pytest.raises(TransientConnectorError):
            await connector.fetch(context(checkpoint=checkpoint))
        recovered = await connector.fetch(context(checkpoint=checkpoint))

    assert checkpoint == {"seen_ids": ["lesson-3", "lesson-2", "lesson-1"]}
    assert [item.external_id for item in recovered.items] == ["lesson-4"]


@pytest.mark.asyncio
async def test_owned_cms_connector_uses_cursor_and_environment_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = json.loads((FIXTURES / "cms_page_1.json").read_text())
    monkeypatch.setenv("OWNED_CMS_TEST_TOKEN", "fixture-token")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["cursor"] == "page-1"
        assert request.headers["Authorization"] == "Bearer fixture-token"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await OwnedCmsConnector(client).fetch(
            context(
                base_url="https://academy.example.test/api/content",
                checkpoint={"cursor": "page-1"},
                connector_config={"credential_env_var": "OWNED_CMS_TEST_TOKEN"},
            )
        )

    assert result.checkpoint == {"cursor": "page-2"}
    assert result.items[0].content_type == ContentType.COURSE


@pytest.mark.asyncio
async def test_owned_cms_rejects_missing_credential() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"items": []}))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(PermanentConnectorError, match="is unset"):
            await OwnedCmsConnector(client).fetch(
                context(connector_config={"credential_env_var": "UNSET_CMS_TOKEN"})
            )


@pytest.mark.asyncio
async def test_youtube_connector_uses_official_api_and_metadata_only() -> None:
    payload = json.loads((FIXTURES / "youtube_search.json").read_text())

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "www.googleapis.com"
        assert request.url.params["channelId"] == "channel-123"
        assert request.url.params["type"] == "video"
        return httpx.Response(200, json=payload)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await YouTubeConnector(client, SecretStr("fixture-key")).fetch(
            context(
                base_url="https://www.youtube.com/@example",
                connector_config={"channel_id": "channel-123"},
            )
        )

    item = result.items[0]
    assert item.content_type == ContentType.VIDEO
    assert str(item.canonical_url) == "https://www.youtube.com/watch?v=official-video-1"
    assert not {"binary", "download_url", "local_path", "storage_key"}.intersection(
        item.raw_metadata
    )
