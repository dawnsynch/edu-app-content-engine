from datetime import UTC, datetime, timedelta

from app.modules.ai.prompts import content_prompt
from app.modules.ai.schemas import EnrichmentDecision
from app.modules.ai.temporal import (
    PublicationDateStatus,
    enforce_publication_policy,
    evaluate_publication_date,
)


def decision(status: str = "safe") -> EnrichmentDecision:
    return EnrichmentDecision.model_validate(
        {
            "topics": ["technology education"],
            "skills": ["career planning"],
            "career_paths": ["software developer"],
            "difficulty": "beginner",
            "quality": {
                "score": 0.8,
                "signals": {
                    "completeness": 0.8,
                    "clarity": 0.8,
                    "authority": 0.8,
                    "freshness": 0.8,
                    "educational_value": 0.8,
                },
            },
            "moderation": {
                "status": status,
                "categories": [],
                "rationale": "Initial assessment.",
            },
            "confidence": 0.9,
        }
    )


def test_past_publication_date_is_deterministically_current() -> None:
    evaluated_at = datetime(2026, 10, 16, 7, 0, tzinfo=UTC)

    context = evaluate_publication_date(
        datetime(2026, 8, 10, 12, 30, tzinfo=UTC),
        evaluated_at=evaluated_at,
    )

    assert context.status == PublicationDateStatus.PAST_OR_PRESENT
    assert context.age_days == 66
    prompt = content_prompt({"title": "Learning", **context.as_prompt_fields()})
    assert "evaluated_at: 2026-10-16T07:00:00+00:00" in prompt
    assert "publication_date_status: past_or_present" in prompt


def test_future_publication_date_forces_review_but_not_rejection() -> None:
    evaluated_at = datetime(2026, 10, 16, 7, 0, tzinfo=UTC)
    context = evaluate_publication_date(
        evaluated_at + timedelta(days=1),
        evaluated_at=evaluated_at,
    )

    governed = enforce_publication_policy(decision(), context)

    assert context.status == PublicationDateStatus.FUTURE
    assert governed.moderation.status.value == "review"
    assert governed.moderation.categories == ["future_publication_date"]


def test_future_publication_date_does_not_downgrade_rejection() -> None:
    evaluated_at = datetime(2026, 10, 16, 7, 0, tzinfo=UTC)
    context = evaluate_publication_date(
        evaluated_at + timedelta(days=1),
        evaluated_at=evaluated_at,
    )

    governed = enforce_publication_policy(decision("reject"), context)

    assert governed.moderation.status.value == "reject"


def test_past_publication_date_clears_false_future_only_review() -> None:
    evaluated_at = datetime(2026, 10, 16, 7, 0, tzinfo=UTC)
    context = evaluate_publication_date(
        datetime(2026, 8, 10, 12, 30, tzinfo=UTC),
        evaluated_at=evaluated_at,
    )
    payload = decision().model_dump()
    payload["moderation"] = {
        "status": "review",
        "categories": ["future publication date discrepancy"],
        "rationale": "The publication date is in the future relative to current date.",
    }
    model_decision = EnrichmentDecision.model_validate(payload)

    governed = enforce_publication_policy(model_decision, context)

    assert governed.moderation.status.value == "safe"
    assert governed.moderation.categories == []


def test_past_publication_date_preserves_non_temporal_review_concerns() -> None:
    evaluated_at = datetime(2026, 10, 16, 7, 0, tzinfo=UTC)
    context = evaluate_publication_date(
        datetime(2026, 8, 10, 12, 30, tzinfo=UTC),
        evaluated_at=evaluated_at,
    )
    payload = decision().model_dump()
    payload["moderation"] = {
        "status": "review",
        "categories": ["future publication date", "ambiguous claims"],
        "rationale": "The date looks future and the claims are ambiguous.",
    }
    model_decision = EnrichmentDecision.model_validate(payload)

    governed = enforce_publication_policy(model_decision, context)

    assert governed.moderation.status.value == "review"
