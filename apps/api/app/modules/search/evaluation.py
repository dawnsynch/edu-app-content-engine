from pathlib import Path

from pydantic import BaseModel, Field

from app.modules.search.schemas import SearchMode


class SearchEvaluationCase(BaseModel):
    id: str
    query: str = Field(min_length=2, max_length=300)
    mode: SearchMode = SearchMode.HYBRID
    relevant_urls: list[str] = Field(min_length=1)


class RankingScore(BaseModel):
    case_id: str
    precision_at_k: float = Field(ge=0, le=1)
    reciprocal_rank: float = Field(ge=0, le=1)
    relevant_retrieved: int = Field(ge=0)


class RankingSummary(BaseModel):
    case_count: int = Field(ge=1)
    mean_precision_at_k: float = Field(ge=0, le=1)
    mean_reciprocal_rank: float = Field(ge=0, le=1)


def load_search_evaluation_cases(path: Path) -> list[SearchEvaluationCase]:
    return [
        SearchEvaluationCase.model_validate_json(line)
        for line in path.read_text().splitlines()
        if line.strip()
    ]


def precision_at_k(relevant: set[str], ranked: list[str], *, k: int) -> float:
    if k < 1:
        raise ValueError("k must be at least 1")
    top_k = list(dict.fromkeys(ranked))[:k]
    return len(relevant.intersection(top_k)) / k


def reciprocal_rank(relevant: set[str], ranked: list[str]) -> float:
    for rank, item in enumerate(dict.fromkeys(ranked), start=1):
        if item in relevant:
            return 1.0 / rank
    return 0.0


def evaluate_ranking(
    case: SearchEvaluationCase,
    ranked_urls: list[str],
    *,
    k: int = 5,
) -> RankingScore:
    relevant = set(case.relevant_urls)
    unique_ranked = list(dict.fromkeys(ranked_urls))
    return RankingScore(
        case_id=case.id,
        precision_at_k=precision_at_k(relevant, unique_ranked, k=k),
        reciprocal_rank=reciprocal_rank(relevant, unique_ranked),
        relevant_retrieved=len(relevant.intersection(unique_ranked)),
    )


def summarize_rankings(scores: list[RankingScore]) -> RankingSummary:
    if not scores:
        raise ValueError("at least one ranking score is required")
    return RankingSummary(
        case_count=len(scores),
        mean_precision_at_k=round(
            sum(score.precision_at_k for score in scores) / len(scores), 6
        ),
        mean_reciprocal_rank=round(
            sum(score.reciprocal_rank for score in scores) / len(scores), 6
        ),
    )
