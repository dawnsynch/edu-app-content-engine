from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.modules.content.models import ContentItem
from app.modules.recommendations.enums import SkillLevel
from app.modules.recommendations.repository import (
    InteractionSummary,
    RecommendationCandidate,
)
from app.modules.recommendations.scoring import diversify, score_candidate


def candidate(
    identifier: int,
    *,
    source_id: int = 1,
    content_type: str = "article",
    topics: list[str] | None = None,
    careers: list[str] | None = None,
    difficulty: str = "beginner",
    quality: str = "0.8",
) -> RecommendationCandidate:
    item = ContentItem(
        id=identifier,
        source_id=source_id,
        canonical_url=f"https://example.test/{identifier}",
        title=f"Learning item {identifier}",
        content_type=content_type,
        status="validated",
        published_at=datetime.now(UTC) - timedelta(days=10),
    )
    return RecommendationCandidate(
        content=item,
        source_name=f"Source {source_id}",
        source_attribution=f"Source {source_id}",
        source_allow_summaries=True,
        source_allow_thumbnails=True,
        topics=topics or [],
        skills=[],
        career_paths=careers or [],
        difficulty=difficulty,
        quality_score=Decimal(quality),
    )


def test_weighted_score_explains_preferences_skill_quality_and_interactions() -> None:
    scored = score_candidate(
        candidate(
            1,
            topics=["python"],
            careers=["software developer"],
            difficulty="beginner",
            quality="0.9",
        ),
        career_preferences=["software developer"],
        technology_domains=["python"],
        skill_level=SkillLevel.BEGINNER,
        interaction=InteractionSummary(bookmarked=True, event_types=("click",)),
        now=datetime.now(UTC),
    )

    assert scored.score > 0.95
    assert scored.matched_careers == ["software developer"]
    assert scored.matched_domains == ["python"]
    assert scored.interaction_signals == ["bookmarked", "click"]
    assert sum(value.weight for value in scored.components.values()) == 1.0
    assert scored.components["quality"].reason == "Permitted source quality assessment."


def test_distinct_preferences_rank_distinct_content() -> None:
    software = candidate(
        1, topics=["python"], careers=["software developer"], difficulty="beginner"
    )
    security = candidate(
        2, topics=["cybersecurity"], careers=["security analyst"], difficulty="advanced"
    )

    beginner_scores = [
        score_candidate(
            item,
            career_preferences=["software developer"],
            technology_domains=["python"],
            skill_level=SkillLevel.BEGINNER,
        )
        for item in (software, security)
    ]
    advanced_scores = [
        score_candidate(
            item,
            career_preferences=["security analyst"],
            technology_domains=["cybersecurity"],
            skill_level=SkillLevel.ADVANCED,
        )
        for item in (software, security)
    ]

    assert max(beginner_scores, key=lambda item: item.score).candidate.content.id == 1
    assert max(advanced_scores, key=lambda item: item.score).candidate.content.id == 2


def test_diversity_moves_repeated_sources_behind_alternatives() -> None:
    ranked = [
        score_candidate(
            candidate(identifier, source_id=1 if identifier < 4 else 2),
            career_preferences=[],
            technology_domains=[],
            skill_level=SkillLevel.BEGINNER,
        )
        for identifier in range(1, 6)
    ]

    diversified, changed = diversify(ranked, target_size=5)

    assert changed is True
    assert [item.candidate.content.source_id for item in diversified[:3]] == [1, 1, 2]
