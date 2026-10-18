from enum import StrEnum


class SourceType(StrEnum):
    WEBSITE = "website"
    RSS = "rss"
    API = "api"
    OWNED_CMS = "owned_cms"
    YOUTUBE = "youtube"
    REPOSITORY = "repository"
    COURSE_PROVIDER = "course_provider"


class SourceStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    BLOCKED = "blocked"


class RightsStatus(StrEnum):
    UNKNOWN = "unknown"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    RESTRICTED = "restricted"
    PROHIBITED = "prohibited"


class StorageMode(StrEnum):
    METADATA_ONLY = "metadata_only"
    SNIPPET = "snippet"
    FULL_TEXT = "full_text"
