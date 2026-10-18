from enum import StrEnum


class SkillLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class EngagementType(StrEnum):
    VIEW = "view"
    CLICK = "click"
    START = "start"
    COMPLETE = "complete"
