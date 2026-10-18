from enum import StrEnum


class IngestionRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class IngestionTrigger(StrEnum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    RETRY = "retry"


class IngestionDisposition(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    REJECTED = "rejected"
