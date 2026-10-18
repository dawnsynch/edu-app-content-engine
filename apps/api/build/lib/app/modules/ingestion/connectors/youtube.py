from datetime import datetime
from typing import Any

import httpx
from pydantic import SecretStr

from app.modules.content.enums import ContentType
from app.modules.ingestion.connectors.base import (
    ConnectorContext,
    ConnectorResult,
    ContentCandidate,
)
from app.modules.ingestion.connectors.errors import PermanentConnectorError
from app.modules.ingestion.connectors.http import raise_for_provider_status

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


class YouTubeConnector:
    def __init__(self, client: httpx.AsyncClient, api_key: SecretStr | None) -> None:
        self.client = client
        self.api_key = api_key

    async def fetch(self, context: ConnectorContext) -> ConnectorResult:
        if self.api_key is None or not self.api_key.get_secret_value():
            raise PermanentConnectorError("YOUTUBE_API_KEY is not configured")
        channel_id = context.connector_config.get("channel_id")
        if not isinstance(channel_id, str) or not channel_id:
            raise PermanentConnectorError("YouTube source requires a channel_id")

        params = {
            "part": "snippet",
            "channelId": channel_id,
            "key": self.api_key.get_secret_value(),
            "maxResults": "50",
            "order": "date",
            "type": "video",
        }
        latest = context.checkpoint.get("latest_published_at")
        if latest:
            params["publishedAfter"] = str(latest)
        candidates: list[ContentCandidate] = []
        newest = str(latest) if latest else None
        max_pages_value = context.connector_config.get("max_pages", 10)
        if not isinstance(max_pages_value, int) or not 1 <= max_pages_value <= 10:
            raise PermanentConnectorError("YouTube max_pages must be between 1 and 10")
        page_token: str | None = None
        for _ in range(max_pages_value):
            if page_token:
                params["pageToken"] = page_token
            response = await self.client.get(YOUTUBE_SEARCH_URL, params=params)
            raise_for_provider_status(response)
            try:
                payload: Any = response.json()
            except ValueError as exc:
                raise PermanentConnectorError("YouTube returned invalid JSON") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
                raise PermanentConnectorError("YouTube returned an invalid response")
            newest = self._append_candidates(payload["items"], candidates, channel_id, newest)
            next_page = payload.get("nextPageToken")
            if not isinstance(next_page, str) or not next_page:
                break
            page_token = next_page

        checkpoint = {"latest_published_at": newest} if newest else context.checkpoint
        return ConnectorResult(items=candidates, checkpoint=checkpoint)

    @staticmethod
    def _append_candidates(
        rows: list[Any],
        candidates: list[ContentCandidate],
        channel_id: str,
        newest: str | None,
    ) -> str | None:
        for row in rows:
            if not isinstance(row, dict):
                continue
            identifier = row.get("id")
            snippet = row.get("snippet")
            if not isinstance(identifier, dict) or not isinstance(snippet, dict):
                continue
            video_id = identifier.get("videoId")
            title = snippet.get("title")
            published_raw = snippet.get("publishedAt")
            if not isinstance(video_id, str) or not isinstance(title, str):
                continue
            published = (
                datetime.fromisoformat(str(published_raw).replace("Z", "+00:00"))
                if published_raw
                else None
            )
            thumbnails = snippet.get("thumbnails")
            thumbnail_url = None
            if isinstance(thumbnails, dict):
                preferred = (
                    thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default")
                )
                if isinstance(preferred, dict) and isinstance(preferred.get("url"), str):
                    thumbnail_url = preferred["url"]
            candidates.append(
                ContentCandidate.model_validate(
                    {
                        "external_id": video_id,
                        "canonical_url": f"https://www.youtube.com/watch?v={video_id}",
                        "title": title,
                        "description": (
                            snippet.get("description")
                            if isinstance(snippet.get("description"), str)
                            else None
                        ),
                        "content_type": ContentType.VIDEO,
                        "author_name": (
                            snippet.get("channelTitle")
                            if isinstance(snippet.get("channelTitle"), str)
                            else None
                        ),
                        "thumbnail_url": thumbnail_url,
                        "published_at": published,
                        "provider_updated_at": published,
                        "raw_metadata": {"provider": "youtube", "channel_id": channel_id},
                    }
                )
            )
            if isinstance(published_raw, str) and (newest is None or published_raw > newest):
                newest = published_raw
        return newest
