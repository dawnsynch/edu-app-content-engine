from pathlib import Path

import pytest

from app.modules.search.evaluation import (
    evaluate_ranking,
    load_search_evaluation_cases,
    precision_at_k,
    reciprocal_rank,
    summarize_rankings,
)

DATASET = Path(__file__).parents[1] / "evals" / "phase3_search_eval.jsonl"


def test_search_evaluation_dataset_uses_stable_relevance_urls() -> None:
    cases = load_search_evaluation_cases(DATASET)

    assert len(cases) >= 4
    assert {case.mode.value for case in cases} == {"hybrid", "semantic"}
    assert all(url.startswith("https://") for case in cases for url in case.relevant_urls)


def test_precision_and_reciprocal_rank_ignore_duplicate_results() -> None:
    relevant = {"https://example.test/relevant", "https://example.test/also-relevant"}
    ranked = [
        "https://example.test/irrelevant",
        "https://example.test/relevant",
        "https://example.test/relevant",
        "https://example.test/also-relevant",
    ]

    assert precision_at_k(relevant, ranked, k=3) == pytest.approx(2 / 3)
    assert reciprocal_rank(relevant, ranked) == 0.5


def test_ranking_summary_reports_precision_at_k_and_mrr() -> None:
    cases = load_search_evaluation_cases(DATASET)[:2]
    scores = [
        evaluate_ranking(cases[0], [cases[0].relevant_urls[0]], k=2),
        evaluate_ranking(
            cases[1],
            ["https://example.test/noise", cases[1].relevant_urls[0]],
            k=2,
        ),
    ]

    summary = summarize_rankings(scores)

    assert summary.case_count == 2
    assert summary.mean_precision_at_k == 0.5
    assert summary.mean_reciprocal_rank == 0.75
