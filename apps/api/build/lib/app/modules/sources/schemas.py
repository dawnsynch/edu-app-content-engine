from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.modules.sources.enums import RightsStatus, SourceStatus, SourceType, StorageMode


class SourcePolicyFields(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    source_type: SourceType
    base_url: HttpUrl
    allowed_domains: list[str] = Field(default_factory=list, max_length=20)
    status: SourceStatus = SourceStatus.DRAFT
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    storage_mode: StorageMode = StorageMode.METADATA_ONLY
    terms_url: HttpUrl | None = None
    license_name: str | None = Field(default=None, max_length=200)
    attribution_required: bool = True
    attribution_text: str | None = Field(default=None, max_length=500)
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    fetch_interval_minutes: int = Field(default=1440, ge=5, le=525600)
    respect_robots_txt: bool = True
    allow_summaries: bool = False
    allow_embeddings: bool = False
    allow_snippets: bool = False
    allow_thumbnails: bool = False
    policy_metadata: dict[str, Any] = Field(default_factory=dict)
    connector_config: dict[str, Any] = Field(default_factory=dict)
    rights_reviewed_at: datetime | None = None
    rights_review_due_at: datetime | None = None

    @field_validator("allowed_domains")
    @classmethod
    def validate_allowed_domains(cls, domains: list[str]) -> list[str]:
        normalized: list[str] = []
        for domain in domains:
            value = domain.strip().lower().rstrip(".")
            if not value or "://" in value or "/" in value:
                raise ValueError("allowed domains must be hostnames without a scheme or path")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @model_validator(mode="after")
    def validate_policy(self) -> "SourcePolicyFields":
        if self.status == SourceStatus.ACTIVE and self.rights_status not in {
            RightsStatus.APPROVED,
            RightsStatus.RESTRICTED,
        }:
            raise ValueError("active sources require approved or restricted rights")

        transformations_allowed = any(
            (
                self.allow_summaries,
                self.allow_embeddings,
                self.allow_snippets,
                self.allow_thumbnails,
            )
        )
        if self.rights_status == RightsStatus.PROHIBITED:
            if self.status == SourceStatus.ACTIVE or transformations_allowed:
                raise ValueError("prohibited sources cannot be active or allow transformations")

        if (
            self.storage_mode == StorageMode.FULL_TEXT
            and self.rights_status != RightsStatus.APPROVED
        ):
            raise ValueError("full-text storage requires approved rights")
        if self.storage_mode == StorageMode.METADATA_ONLY and self.allow_snippets:
            raise ValueError("metadata-only sources cannot retain snippets")
        if self.attribution_required and not self.attribution_text:
            raise ValueError("attribution text is required when attribution is required")
        if (
            self.rights_reviewed_at
            and self.rights_review_due_at
            and self.rights_review_due_at <= self.rights_reviewed_at
        ):
            raise ValueError("rights review due date must be after the reviewed date")

        forbidden_config_keys = {
            "api_key",
            "authorization",
            "password",
            "secret",
            "token",
        }
        present = forbidden_config_keys.intersection(key.lower() for key in self.connector_config)
        if present:
            raise ValueError(
                "connector configuration may reference environment variables, not secrets"
            )

        if self.source_type == SourceType.YOUTUBE:
            channel_id = self.connector_config.get("channel_id")
            if not isinstance(channel_id, str) or not channel_id.strip():
                raise ValueError("YouTube sources require connector_config.channel_id")
        if self.source_type == SourceType.OWNED_CMS:
            credential_env = self.connector_config.get("credential_env_var")
            if credential_env is not None and (
                not isinstance(credential_env, str) or not credential_env.isidentifier()
            ):
                raise ValueError("credential_env_var must be a valid environment variable name")
        return self


class SourceCreate(SourcePolicyFields):
    pass


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    source_type: SourceType | None = None
    base_url: HttpUrl | None = None
    allowed_domains: list[str] | None = Field(default=None, max_length=20)
    status: SourceStatus | None = None
    rights_status: RightsStatus | None = None
    storage_mode: StorageMode | None = None
    terms_url: HttpUrl | None = None
    license_name: str | None = Field(default=None, max_length=200)
    attribution_required: bool | None = None
    attribution_text: str | None = Field(default=None, max_length=500)
    retention_days: int | None = Field(default=None, ge=1, le=3650)
    fetch_interval_minutes: int | None = Field(default=None, ge=5, le=525600)
    respect_robots_txt: bool | None = None
    allow_summaries: bool | None = None
    allow_embeddings: bool | None = None
    allow_snippets: bool | None = None
    allow_thumbnails: bool | None = None
    policy_metadata: dict[str, Any] | None = None
    connector_config: dict[str, Any] | None = None
    rights_reviewed_at: datetime | None = None
    rights_review_due_at: datetime | None = None


class SourceResponse(SourcePolicyFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


class SourceListResponse(BaseModel):
    items: list[SourceResponse]
    next_cursor: int | None
