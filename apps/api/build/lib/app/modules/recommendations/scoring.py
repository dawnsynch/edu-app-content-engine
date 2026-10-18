from dataclasses import dataclass
from datetime import UTC, datetime
from math import ceil

from app.modules.recommendations.enums import SkillLevel
from app.modules.recommendations.repository import (
    InteractionSummary,
    RecommendationCandidate,
)

WEIGHTS = {
    "career_relevance": 0.25,
    "domain_relevance": 0.20,
    "skill_level_fit": 0.15,
    "quality": 0.20,
    "freshness": 0.10,
    "interactions": 0.10,
}


@dataclass(frozen=True)
class ComponentScore:
    weight: float
    value: float
    contribution: float
    reason: str


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: RecommendationCandidate
    score: float
    components: dict[str, ComponentScore]
    matched_careers: list[str]
    matched_domains: list[str]
    interaction_signals: list[str]


def _terms(values: list[str]) -> set[str]:
    return {" ".join(value.lower().split()) for value in values if value.strip()}


def _match_score(preferences: list[str], labels: list[str], title: str) -> tuple[float, list[str]]:
    if not preferences:
        return 0.5, []
    haystack = " ".join([*_terms(labels), title.lower()])
    matches = [preference for preference in _terms(preferences) if preference in haystack]
    return min(1.0, len(matches) / len(set(preferences))), sorted(matches)


def _skill_score(learner_level: SkillLevel, content_level: str | None) -> tuple[float, str]:
    if content_level is None:
        return 0.5, "Content skill level is not classified."
    if content_level == "mixed":
        return 0.75, "Mixed-level content can support this learner level."
    order = {"beginner": 0, "intermediate": 1, "advanced": 2}
    distance = abs(order[learner_level.value] - order.get(content_level, 1))
    score = {0: 1.0, 1: 0.55, 2: 0.15}[distance]
    return score, f"Learner is {learner_level.value}; content is {content_level}."


def _freshness_score(published_at: datetime | None, now: datetime) -> tuple[float, str]:
    if published_at is None:
        return 0.5, "Publication date is unavailable."
    published = published_at if published_at.tzinfo else published_at.replace(tzinfo=UTC)
    age_days = max(0, (now - published.astimezone(UTC)).days)
    if age_days <= 30:
        score = 1.0
    elif age_days <= 90:
        score = 0.8
    elif age_days <= 180:
        score = 0.6
    elif age_days <= 365:
        score = 0.4
    else:
        score = 0.2
    return score, f"Published {age_days} days ago."


def _interaction_score(interaction: InteractionSummary) -> tuple[float, list[str]]:
    signals: list[str] = []
    values = {"view": 0.4, "click": 0.55, "start": 0.75, "complete": 1.0}
    score = 0.25
    for event_type in interaction.event_types:
        signals.append(event_type)
        score = max(score, values.get(event_type, 0.25))
    if interaction.bookmarked:
        signals.append("bookmarked")
        score = 1.0
    return score, sorted(signals)


def score_candidate(
    candidate: RecommendationCandidate,
    *,
    career_preferences: list[str],
    technology_domains: list[str],
    skill_level: SkillLevel,
    interaction: InteractionSummary | None = None,
    now: datetime | None = None,
) -> ScoredCandidate:
    effective_now = now or datetime.now(UTC)
    interaction = interaction or InteractionSummary()
    labels = [*candidate.topics, *candidate.skills]
    career, matched_careers = _match_score(
        career_preferences, candidate.career_paths, candidate.content.title
    )
    domain, matched_domains = _match_score(
        technology_domains, labels, candidate.content.title
    )
    skill, skill_reason = _skill_score(skill_level, candidate.difficulty)
    quality = float(candidate.quality_score) if candidate.quality_score is not None else 0.5
    freshness, freshness_reason = _freshness_score(candidate.content.published_at, effective_now)
    interactions, interaction_signals = _interaction_score(interaction)
    values = {
        "career_relevance": (
            career,
            "Matched learner career preferences."
            if matched_careers
            else "No explicit career match.",
        ),
        "domain_relevance": (
            domain,
            "Matched selected technology domains."
            if matched_domains
            else "No explicit technology-domain match.",
        ),
        "skill_level_fit": (skill, skill_reason),
        "quality": (quality, "Permitted source quality assessment."),
        "freshness": (freshness, freshness_reason),
        "interactions": (interactions, "Uses bookmark and anonymous engagement signals."),
    }
    components = {
        name: ComponentScore(
            weight=WEIGHTS[name],
            value=round(value, 4),
            contribution=round(value * WEIGHTS[name], 4),
            reason=reason,
        )
        for name, (value, reason) in values.items()
    }
    score = min(1.0, sum(component.contribution for component in components.values()))
    return ScoredCandidate(
        candidate=candidate,
        score=round(score, 6),
        components=components,
        matched_careers=matched_careers,
        matched_domains=matched_domains,
        interaction_signals=interaction_signals,
    )


def diversify(
    ranked: list[ScoredCandidate], *, target_size: int
) -> tuple[list[ScoredCandidate], bool]:
    if len(ranked) < 2:
        return ranked, False
    source_limit = max(2, ceil(target_size * 0.3))
    type_limit = max(3, ceil(target_size * 0.5))
    selected: list[ScoredCandidate] = []
    deferred: list[ScoredCandidate] = []
    source_counts: dict[int, int] = {}
    type_counts: dict[str, int] = {}
    for item in ranked:
        source_id = item.candidate.content.source_id
        content_type = item.candidate.content.content_type
        source_full = source_counts.get(source_id, 0) >= source_limit
        type_full = type_counts.get(content_type, 0) >= type_limit
        if source_full or type_full:
            deferred.append(item)
            continue
        selected.append(item)
        source_counts[source_id] = source_counts.get(source_id, 0) + 1
        type_counts[content_type] = type_counts.get(content_type, 0) + 1
    result = [*selected, *deferred]
    changed = [item.candidate.content.id for item in result] != [
        item.candidate.content.id for item in ranked
    ]
    return result, changed
