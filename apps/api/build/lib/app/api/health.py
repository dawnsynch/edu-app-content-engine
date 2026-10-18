from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings, get_settings
from app.db.session import get_db_session

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: str


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    redis: Literal["ok", "unavailable"]
    qdrant: Literal["ok", "unavailable"]
    litellm: Literal["ok", "unavailable"]


async def dependency_http_status(url: str) -> Literal["ok", "unavailable"]:
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(url)
            response.raise_for_status()
    except (httpx.HTTPError, OSError):
        return "unavailable"
    return "ok"


@router.get("/live", response_model=HealthResponse)
async def live(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", service="edu-dawnsynch-api", environment=settings.app_env)


@router.get("/ready", response_model=ReadinessResponse)
async def ready(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ReadinessResponse:
    database_status: Literal["ok", "unavailable"] = "ok"
    redis_status: Literal["ok", "unavailable"] = "ok"

    try:
        await session.execute(text("select 1"))
    except Exception:
        database_status = "unavailable"

    redis_client = Redis.from_url(settings.redis_url)
    try:
        await redis_client.ping()
    except Exception:
        redis_status = "unavailable"
    finally:
        await redis_client.aclose()

    qdrant_status = await dependency_http_status(f"{settings.qdrant_url}/readyz")
    litellm_status = await dependency_http_status(f"{settings.litellm_base_url}/health/liveliness")

    overall: Literal["ok", "degraded"] = (
        "ok"
        if all(
            status == "ok"
            for status in (database_status, redis_status, qdrant_status, litellm_status)
        )
        else "degraded"
    )
    return ReadinessResponse(
        status=overall,
        database=database_status,
        redis=redis_status,
        qdrant=qdrant_status,
        litellm=litellm_status,
    )
