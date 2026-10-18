import argparse
import asyncio
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.modules.search.evaluation import (
    RankingScore,
    RankingSummary,
    evaluate_ranking,
    load_search_evaluation_cases,
    summarize_rankings,
)
from app.modules.search.schemas import SearchResponse


class LiveEvaluationReport(BaseModel):
    base_url: str
    k: int
    scores: list[RankingScore]
    summary: RankingSummary


async def evaluate_live(base_url: str, dataset: Path, *, k: int) -> LiveEvaluationReport:
    cases = load_search_evaluation_cases(dataset)
    scores: list[RankingScore] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=30) as client:
        for case in cases:
            response = await client.get(
                "/api/v1/search",
                params={"q": case.query, "mode": case.mode.value, "limit": max(k, 10)},
            )
            response.raise_for_status()
            result = SearchResponse.model_validate(response.json())
            scores.append(
                evaluate_ranking(
                    case,
                    [item.content.canonical_url for item in result.items],
                    k=k,
                )
            )
    return LiveEvaluationReport(
        base_url=base_url,
        k=k,
        scores=scores,
        summary=summarize_rankings(scores),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the live Phase 3 search ranking")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path(__file__).parents[3] / "evals" / "phase3_search_eval.jsonl",
    )
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()
    if args.k < 1:
        parser.error("k must be at least 1")
    report = asyncio.run(evaluate_live(args.base_url, args.dataset, k=args.k))
    print(report.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
