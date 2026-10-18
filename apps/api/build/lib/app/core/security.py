from hmac import compare_digest
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.core.settings import Settings, get_settings


async def require_admin(
    settings: Annotated[Settings, Depends(get_settings)],
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> None:
    configured_key = settings.admin_api_key
    if configured_key is None or not configured_key.get_secret_value():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative API is not configured",
        )

    if x_admin_key is None or not compare_digest(
        x_admin_key.encode(), configured_key.get_secret_value().encode()
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrative API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
