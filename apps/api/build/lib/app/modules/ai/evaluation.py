from pathlib import Path

from pydantic import BaseModel, Field

from app.modules.ai.schemas import Difficulty, EnrichmentDecision, ModerationStatus


class EvaluationInput(BaseModel):
    title: str
    description: str | None = None
    content_type: str
    author_name: str | None = None


class EvaluationExpected(BaseModel):
    required_topics: list[str]
    difficulty: Difficulty
    moderation_status: ModerationStatus
    quality_score_min: float = Field(ge=0, le=1)
    quality_score_max: float = Field(ge=0, le=1)


class EvaluationCase(BaseModel):
    id: str
    input: EvaluationInput
    expected: EvaluationExpected


class EvaluationScore(BaseModel):
    case_id: str
    passed: bool
    topic_recall: float
    difficulty_match: bool
    moderation_match: bool
    quality_in_range: bool


def load_evaluation_cases(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line in path.read_text().splitlines():
        if line.strip():
            cases.append(EvaluationCase.model_validate_json(line))
    return cases


def evaluate_decision(case: EvaluationCase, decision: EnrichmentDecision) -> EvaluationScore:
    required = set(case.expected.required_topics)
    actual = set(decision.topics)
    recall = len(required.intersection(actual)) / len(required) if required else 1.0
    difficulty_match = decision.difficulty == case.expected.difficulty
    moderation_match = decision.moderation.status == case.expected.moderation_status
    quality_in_range = (
        case.expected.quality_score_min <= decision.quality.score <= case.expected.quality_score_max
    )
    return EvaluationScore(
        case_id=case.id,
        passed=(recall == 1.0 and difficulty_match and moderation_match and quality_in_range),
        topic_recall=recall,
        difficulty_match=difficulty_match,
        moderation_match=moderation_match,
        quality_in_range=quality_in_range,
    )
