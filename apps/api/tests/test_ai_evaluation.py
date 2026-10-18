from pathlib import Path

from app.modules.ai.evaluation import evaluate_decision, load_evaluation_cases
from app.modules.ai.schemas import EnrichmentDecision

DATASET = Path(__file__).parents[1] / "evals" / "phase3_content_eval.jsonl"


def test_evaluation_dataset_is_valid_and_covers_risk_states() -> None:
    cases = load_evaluation_cases(DATASET)

    assert len(cases) >= 6
    assert {case.expected.moderation_status.value for case in cases} == {
        "safe",
        "review",
        "reject",
    }


def test_evaluator_scores_required_dimensions() -> None:
    case = load_evaluation_cases(DATASET)[0]
    decision = EnrichmentDecision.model_validate(
        {
            "topics": ["python", "programming fundamentals"],
            "skills": ["loops"],
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
                "status": "safe",
                "categories": [],
                "rationale": "Safe educational material.",
            },
            "confidence": 0.9,
        }
    )

    score = evaluate_decision(case, decision)

    assert score.passed is True
    assert score.topic_recall == 1.0
