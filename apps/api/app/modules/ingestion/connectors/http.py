import httpx

from app.modules.ingestion.connectors.errors import (
    PermanentConnectorError,
    TransientConnectorError,
)


def raise_for_provider_status(response: httpx.Response) -> None:
    if response.status_code == 429 or response.status_code >= 500:
        raise TransientConnectorError(f"provider returned HTTP {response.status_code}")
    if response.status_code >= 400:
        raise PermanentConnectorError(f"provider returned HTTP {response.status_code}")
