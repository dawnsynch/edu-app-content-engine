from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.modules.ingestion.enums import IngestionRunStatus, IngestionTrigger


class IngestionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    trigger: IngestionTrigger
    status: IngestionRunStatus
    attempt: int
    checkpoint_before: dict[str, Any]
    checkpoint_after: dict[str, Any] | None
    discovered_count: int
    created_count: int
    updated_count: int
    unchanged_count: int
    rejected_count: int
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class IngestionRunListResponse(BaseModel):
    items: list[IngestionRunResponse]
    next_cursor: int | None


class SourceHealthResponse(BaseModel):
    source_id: int
    checkpoint: dict[str, Any]
    last_attempted_at: datetime | None
    last_succeeded_at: datetime | None
    next_due_at: datetime | None
    consecutive_failures: int
    total_successes: int
    total_failures: int
    last_status: str | None
    last_error_code: str | None
    last_error_message: str | None
    last_duration_ms: int | None


class IngestionTaskResponse(BaseModel):
    source_id: int
    task_id: str
    status: str = "queued"
