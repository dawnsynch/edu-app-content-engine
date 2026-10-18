import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from app.core.security import require_admin
from app.core.settings import Settings


@pytest.mark.asyncio
async def test_admin_key_is_required() -> None:
    settings = Settings(admin_api_key=SecretStr("test-secret"))

    with pytest.raises(HTTPException) as exc_info:
        await require_admin(settings=settings, x_admin_key=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_valid_admin_key_is_accepted() -> None:
    settings = Settings(admin_api_key=SecretStr("test-secret"))

    await require_admin(settings=settings, x_admin_key="test-secret")


@pytest.mark.asyncio
async def test_admin_api_is_disabled_without_configuration() -> None:
    settings = Settings(admin_api_key=None)

    with pytest.raises(HTTPException) as exc_info:
        await require_admin(settings=settings, x_admin_key="anything")

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_admin_api_is_disabled_for_empty_compose_value() -> None:
    settings = Settings(admin_api_key=SecretStr(""))

    with pytest.raises(HTTPException) as exc_info:
        await require_admin(settings=settings, x_admin_key="anything")

    assert exc_info.value.status_code == 503
