import os
from typing import Any

import httpx
from pydantic import ValidationError

from app.modules.content.validators import validate_source_host
from app.modules.ingestion.connectors.base import (
    ConnectorContext,
    ConnectorResult,
    ContentCandidate,
)
from app.modules.ingestion.connectors.errors import PermanentConnectorError
from app.modules.ingestion.connectors.http import raise_for_provider_status


class OwnedCmsConnector:
    """Connector for the documented first-party `{items, next_cursor}` JSON contract."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, context: ConnectorContext) -> ConnectorResult:
        headers = {"Accept": "application/json"}
        credential_env = context.connector_config.get("credential_env_var")
        if credential_env:
            credential = os.getenv(str(credential_env))
            if not credential:
                raise PermanentConnectorError(
                    f"required credential environment {credential_env} is unset"
                )
            headers["Authorization"] = f"Bearer {credential}"

        params: dict[str, str] = {}
        cursor = context.checkpoint.get("cursor")
        if cursor is not None:
            params["cursor"] = str(cursor)
        response = await self.client.get(
            str(context.base_url),
            headers=headers,
            params=params,
            follow_redirects=True,
        )
        validate_source_host(str(response.url), str(context.base_url), context.allowed_domains)
        raise_for_provider_status(response)
        try:
            payload: Any = response.json()
        except ValueError as exc:
            raise PermanentConnectorError("owned CMS returned invalid JSON") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise PermanentConnectorError("owned CMS response must contain an items array")

        try:
            items = [ContentCandidate.model_validate(item) for item in payload["items"]]
        except ValidationError as exc:
            raise PermanentConnectorError("owned CMS returned an invalid content item") from exc
        next_cursor = payload.get("next_cursor", cursor)
        checkpoint = {"cursor": next_cursor} if next_cursor is not None else {}
        return ConnectorResult(items=items, checkpoint=checkpoint)
