from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from app.modules.ai.schemas import (
    EnrichmentDecision,
    ModerationAssessment,
    ModerationStatus,
)


class PublicationDateStatus(StrEnum):
    UNKNOWN = "unknown"
    PAST_OR_PRESENT = "past_or_present"
    FUTURE = "future"


@dataclass(frozen=True)
class PublicationContext:
    evaluated_at: datetime
    status: PublicationDateStatus
    age_days: int | None

    def as_prompt_fields(self) -> dict[str, object]:
        return {
            "evaluated_at": self.evaluated_at.isoformat(),
            "publication_date_status": self.status.value,
            "publication_age_days": self.age_days,
        }


def evaluate_publication_date(
    published_at: datetime | None,
    *,
    evaluated_at: datetime | None = None,
    clock_skew: timedelta = timedelta(minutes=5),
) -> PublicationContext:
    now = evaluated_at or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)
    if published_at is None:
        return PublicationContext(now, PublicationDateStatus.UNKNOWN, None)

    published = published_at.replace(tzinfo=published_at.tzinfo or UTC).astimezone(UTC)
    if published > now + clock_skew:
        return PublicationContext(now, PublicationDateStatus.FUTURE, None)
    return PublicationContext(
        now,
        PublicationDateStatus.PAST_OR_PRESENT,
        max(0, (now - published).days),
    )


def enforce_publication_policy(
    decision: EnrichmentDecision,
    context: PublicationContext,
) -> EnrichmentDecision:
    if context.status == PublicationDateStatus.PAST_OR_PRESENT and _is_false_future_review(
        decision.moderation
    ):
        moderation = ModerationAssessment(
            status=ModerationStatus.SAFE,
            categories=[],
            rationale=(
                "Deterministic UTC publication-date validation passed; no other moderation "
                "concern was identified."
            ),
        )
        return decision.model_copy(update={"moderation": moderation})

    if context.status != PublicationDateStatus.FUTURE or (
        decision.moderation.status == ModerationStatus.REJECT
    ):
        return decision

    categories = list(dict.fromkeys([*decision.moderation.categories, "future_publication_date"]))
    moderation = ModerationAssessment(
        status=ModerationStatus.REVIEW,
        categories=categories,
        rationale=(
            "The publication timestamp is later than the deterministic UTC evaluation time; "
            "verify the provider metadata before approval."
        ),
    )
    return decision.model_copy(update={"moderation": moderation})


def _is_false_future_review(moderation: ModerationAssessment) -> bool:
    if moderation.status != ModerationStatus.REVIEW:
        return False

    def is_temporal(value: str) -> bool:
        normalized = value.lower()
        return "future" in normalized and any(
            term in normalized for term in ("date", "publication", "publish")
        )

    if moderation.categories and not all(is_temporal(item) for item in moderation.categories):
        return False
    rationale = moderation.rationale.lower()
    disqualifying_concerns = {
        "adult",
        "ambiguous",
        "deceptive",
        "harm",
        "hate",
        "illegal",
        "leaked",
        "misinformation",
        "unrelated",
        "unsafe",
        "violence",
    }
    return is_temporal(rationale) and not any(
        concern in rationale for concern in disqualifying_concerns
    )
