from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import monotonic

import httpx
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PolicyViolationError, ResourceNotFoundError
from app.core.settings import Settings
from app.modules.content.schemas import ContentCreate
from app.modules.content.service import ContentService
from app.modules.ingestion.connectors import ConnectorContext, ConnectorRegistry, ContentCandidate
from app.modules.ingestion.connectors.errors import (
    ConnectorError,
    PermanentConnectorError,
    TransientConnectorError,
)
from app.modules.ingestion.enums import IngestionTrigger
from app.modules.ingestion.models import IngestionRun, SourceSyncState
from app.modules.ingestion.repository import IngestionRepository
from app.modules.sources.enums import RightsStatus, SourceStatus
from app.modules.sources.repository import SourceRepository


def candidate_fingerprint(candidate: ContentCandidate) -> str:
    values = (
        candidate.title.strip().lower(),
        (candidate.description or "").strip().lower(),
        (candidate.author_name or "").strip().lower(),
        candidate.published_at.isoformat() if candidate.published_at else "",
    )
    return sha256("\x1f".join(values).encode()).hexdigest()


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = IngestionRepository(session)
        self.sources = SourceRepository(session)
        self.content = ContentService(session)

    async def get_run(self, run_id: int) -> IngestionRun:
        run = await self.repository.get_run(run_id)
        if run is None:
            raise ResourceNotFoundError("ingestion run not found")
        return run

    async def list_runs(
        self,
        *,
        after_id: int | None,
        limit: int,
        source_id: int | None,
        status: str | None,
    ) -> tuple[list[IngestionRun], int | None]:
        rows = await self.repository.list_runs(
            after_id=after_id,
            limit=limit,
            source_id=source_id,
            status=status,
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        return items, items[-1].id if has_more and items else None

    async def get_health(self, source_id: int) -> SourceSyncState:
        if await self.sources.get(source_id) is None:
            raise ResourceNotFoundError("source not found")
        state = await self.repository.get_state(source_id)
        return state or SourceSyncState(
            source_id=source_id,
            checkpoint={},
            consecutive_failures=0,
            total_successes=0,
            total_failures=0,
        )

    async def ingest(
        self,
        source_id: int,
        *,
        trigger: IngestionTrigger,
        attempt: int,
        client: httpx.AsyncClient,
        settings: Settings,
    ) -> IngestionRun:
        source = await self.sources.get(source_id)
        if source is None:
            raise ResourceNotFoundError("source not found")
        if source.status != SourceStatus.ACTIVE:
            raise PolicyViolationError("ingestion requires an active source")
        if source.rights_status not in {RightsStatus.APPROVED, RightsStatus.RESTRICTED}:
            raise PolicyViolationError("ingestion requires approved source rights")

        state = await self.repository.get_or_create_state(source_id)
        started_at = datetime.now(UTC)
        run = IngestionRun(
            source_id=source_id,
            trigger=trigger.value,
            status="running",
            attempt=attempt,
            checkpoint_before=dict(state.checkpoint),
            started_at=started_at,
        )
        await self.repository.add_run(run)
        state.last_attempted_at = started_at
        state.last_status = "running"
        state.next_due_at = started_at + timedelta(minutes=source.fetch_interval_minutes)
        await self.session.commit()
        started = monotonic()

        try:
            connector = ConnectorRegistry(client, settings).get(source.source_type)
            result = await connector.fetch(
                ConnectorContext.model_validate(
                    {
                        "source_id": source.id,
                        "base_url": source.base_url,
                        "allowed_domains": source.allowed_domains,
                        "connector_config": source.connector_config,
                        "checkpoint": state.checkpoint,
                        "etag": state.etag,
                        "last_modified": state.last_modified,
                    }
                )
            )
            run.discovered_count = len(result.items)
            for candidate in result.items:
                try:
                    candidate_data = candidate.model_dump(mode="python")
                    if not source.allow_summaries and not source.allow_snippets:
                        candidate_data["description"] = None
                    if not source.allow_thumbnails:
                        candidate_data["thumbnail_url"] = None
                    governed_candidate = ContentCandidate.model_validate(candidate_data)
                    payload = ContentCreate(
                        source_id=source_id,
                        content_fingerprint=candidate_fingerprint(governed_candidate),
                        **governed_candidate.model_dump(mode="python"),
                    )
                    _, disposition = await self.content.upsert_ingested(payload)
                    setattr(run, f"{disposition}_count", getattr(run, f"{disposition}_count") + 1)
                except (PolicyViolationError, ValidationError):
                    run.rejected_count += 1

            now = datetime.now(UTC)
            run.status = "succeeded"
            run.checkpoint_after = result.checkpoint
            run.finished_at = now
            state.checkpoint = result.checkpoint
            state.etag = result.etag
            state.last_modified = result.last_modified
            state.last_succeeded_at = now
            state.next_due_at = now + timedelta(minutes=source.fetch_interval_minutes)
            state.consecutive_failures = 0
            state.total_successes += 1
            state.last_status = "succeeded"
            state.last_error_code = None
            state.last_error_message = None
            state.last_duration_ms = int((monotonic() - started) * 1000)
            await self.session.commit()
            await self.session.refresh(run)
            return run
        except httpx.HTTPError as exc:
            transient_error = TransientConnectorError("provider request failed")
            await self._record_failure(
                run, state, source.fetch_interval_minutes, transient_error, started
            )
            raise transient_error from exc
        except ConnectorError as exc:
            await self._record_failure(run, state, source.fetch_interval_minutes, exc, started)
            raise
        except Exception as exc:
            permanent_error = PermanentConnectorError("unexpected ingestion failure")
            await self._record_failure(
                run, state, source.fetch_interval_minutes, permanent_error, started
            )
            raise permanent_error from exc

    async def _record_failure(
        self,
        run: IngestionRun,
        state: SourceSyncState,
        fetch_interval_minutes: int,
        error: ConnectorError,
        started: float,
    ) -> None:
        now = datetime.now(UTC)
        run.status = "failed"
        run.error_code = error.code
        run.error_message = str(error)[:2000]
        run.finished_at = now
        state.consecutive_failures += 1
        state.total_failures += 1
        state.last_status = "failed"
        state.last_error_code = error.code
        state.last_error_message = str(error)[:2000]
        state.last_duration_ms = int((monotonic() - started) * 1000)
        retry_delay = min(fetch_interval_minutes, 5 * (2 ** (state.consecutive_failures - 1)))
        state.next_due_at = now + timedelta(minutes=retry_delay)
        await self.session.commit()
