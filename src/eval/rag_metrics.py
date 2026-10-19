"""RAGAS-style metrics: faithfulness, relevancy, context precision."""

from __future__ import annotations

from typing import Any


def evaluate_rag(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str] | None = None,
) -> dict[str, Any]:
    """Compute evaluation metrics over a golden set."""
    _ = (questions, answers, contexts, ground_truths)
    return {
        "faithfulness": None,
        "answer_relevancy": None,
        "context_precision": None,
        "n_samples": len(questions),
    }
