from enum import StrEnum


class ContentType(StrEnum):
    ARTICLE = "article"
    VIDEO = "video"
    COURSE = "course"
    TUTORIAL = "tutorial"
    PODCAST = "podcast"
    REPOSITORY = "repository"
    DOCUMENTATION = "documentation"
    EVENT = "event"
    OTHER = "other"


class ContentStatus(StrEnum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    REJECTED = "rejected"
    EXPIRED = "expired"
