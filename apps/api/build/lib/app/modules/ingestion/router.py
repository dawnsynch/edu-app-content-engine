from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PolicyViolationError
from app.core.security import require_admin
from app.db.session import get_db_session
from app.modules.ingestion.enums import IngestionRunStatus
from app.modules.ingestion.schemas import (
    IngestionRunListResponse,
    IngestionRunResponse,
    IngestionTaskResponse,
    SourceHealthResponse,
)
from app.modules.ingestion.service import IngestionService
from app.modules.sources.enums import RightsStatus, SourceStatus, SourceType
from app.modules.sources.service import SourceService
from app.worker.tasks import run_source_ingestion

router = APIRouter(tags=["admin-ingestion"], dependencies=[Depends(require_admin)])


@router.post(
    "/api/v1/admin/sources/{source_id}/ingest",
    response_model=IngestionTaskResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_ingestion(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IngestionTaskResponse:
    source = await SourceService(session).get(source_id)
    if source.status != SourceStatus.ACTIVE or source.rights_status not in {
        RightsStatus.APPROVED,
        RightsStatus.RESTRICTED,
    }:
        raise PolicyViolationError("ingestion requires an active source with approved rights")
    if source.source_type not in {
        SourceType.RSS,
        SourceType.OWNED_CMS,
        SourceType.YOUTUBE,
    }:
        raise PolicyViolationError("source type does not support automated ingestion")
    task = run_source_ingestion.delay(source_id, "manual")
    return IngestionTaskResponse(source_id=source_id, task_id=str(task.id))


@router.get(
    "/api/v1/admin/sources/{source_id}/health",
    response_model=SourceHealthResponse,
)
async def source_health(
    source_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SourceHealthResponse:
    state = await IngestionService(session).get_health(source_id)
    return SourceHealthResponse.model_validate(state, from_attributes=True)


@router.get("/api/v1/admin/ingestion/runs", response_model=IngestionRunListResponse)
async def list_ingestion_runs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    after_id: Annotated[int | None, Query(gt=0)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    source_id: Annotated[int | None, Query(gt=0)] = None,
    run_status: Annotated[IngestionRunStatus | None, Query(alias="status")] = None,
) -> IngestionRunListResponse:
    items, next_cursor = await IngestionService(session).list_runs(
        after_id=after_id,
        limit=limit,
        source_id=source_id,
        status=run_status.value if run_status else None,
    )
    return IngestionRunListResponse(
        items=[IngestionRunResponse.model_validate(item) for item in items],
        next_cursor=next_cursor,
    )


@router.get("/api/v1/admin/ingestion/runs/{run_id}", response_model=IngestionRunResponse)
async def get_ingestion_run(
    run_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IngestionRunResponse:
    return IngestionRunResponse.model_validate(await IngestionService(session).get_run(run_id))
