from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx
from pydantic import ValidationError

from app.modules.content.enums import ContentType
from app.modules.content.validators import validate_source_host
from app.modules.ingestion.connectors.base import (
    ConnectorContext,
    ConnectorResult,
    ContentCandidate,
)
from app.modules.ingestion.connectors.errors import PermanentConnectorError
from app.modules.ingestion.connectors.http import raise_for_provider_status


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ElementTree.Element, *names: str) -> str | None:
    wanted = set(names)
    for child in element:
        if _local_name(child.tag) in wanted and child.text:
            return child.text.strip()
    return None


def _entry_link(element: ElementTree.Element) -> str | None:
    for child in element:
        if _local_name(child.tag) != "link":
            continue
        href = child.attrib.get("href")
        relation = child.attrib.get("rel", "alternate")
        if href and relation == "alternate":
            return href.strip()
        if child.text:
            return child.text.strip()
    return None


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=parsed.tzinfo or UTC)


class RssAtomConnector:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, context: ConnectorContext) -> ConnectorResult:
        headers: dict[str, str] = {
            "Accept": "application/atom+xml, application/rss+xml, application/xml"
        }
        if context.etag:
            headers["If-None-Match"] = context.etag
        if context.last_modified:
            headers["If-Modified-Since"] = context.last_modified

        response = await self.client.get(
            str(context.base_url), headers=headers, follow_redirects=True
        )
        validate_source_host(str(response.url), str(context.base_url), context.allowed_domains)
        if response.status_code == 304:
            return ConnectorResult(
                checkpoint=context.checkpoint,
                etag=context.etag,
                last_modified=context.last_modified,
                not_modified=True,
            )
        raise_for_provider_status(response)
        if b"<!DOCTYPE" in response.content.upper():
            raise PermanentConnectorError("RSS/Atom documents containing a DOCTYPE are rejected")
        try:
            root = ElementTree.fromstring(response.content)
        except ElementTree.ParseError as exc:
            raise PermanentConnectorError("provider returned invalid RSS/Atom XML") from exc

        entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
        previous_ids = [str(value) for value in context.checkpoint.get("seen_ids", [])]
        seen = set(previous_ids)
        current_ids: list[str] = []
        items: list[ContentCandidate] = []
        configured_type = context.connector_config.get("content_type", ContentType.ARTICLE.value)
        try:
            content_type = ContentType(str(configured_type))
        except ValueError as exc:
            raise PermanentConnectorError("invalid RSS connector content_type") from exc

        for entry in entries:
            link = _entry_link(entry)
            title = _child_text(entry, "title")
            external_id = _child_text(entry, "guid", "id") or link
            if not link or not title or not external_id:
                continue
            if external_id in seen:
                current_ids.append(external_id)
                continue
            published = _parse_date(_child_text(entry, "published", "pubdate", "updated"))
            try:
                candidate = ContentCandidate.model_validate(
                    {
                        "external_id": external_id,
                        "canonical_url": link,
                        "title": title,
                        "description": _child_text(entry, "summary", "description"),
                        "content_type": content_type,
                        "author_name": _child_text(entry, "author", "creator"),
                        "published_at": published,
                        "provider_updated_at": published,
                        "raw_metadata": {"provider": "rss_atom"},
                    }
                )
            except ValidationError:
                continue
            current_ids.append(external_id)
            items.append(candidate)

        next_seen = list(dict.fromkeys(current_ids + previous_ids))[:500]
        return ConnectorResult(
            items=items,
            checkpoint={"seen_ids": next_seen},
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )
