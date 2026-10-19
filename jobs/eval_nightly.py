"""Job: nightly evaluation against the golden set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.eval.rag_metrics import evaluate_rag
from src.observability.tracing import setup_logging


def load_golden_set(eval_dir: str = "data/eval") -> dict:
    path = Path(eval_dir) / "golden.json"
    if not path.exists():
        return {"questions": [], "answers": [], "contexts": [], "ground_truths": []}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    setup_logging()
    data = load_golden_set()
    metrics = evaluate_rag(
        questions=data.get("questions", []),
        answers=data.get("answers", []),
        contexts=data.get("contexts", []),
        ground_truths=data.get("ground_truths"),
    )
    print(f"Nightly eval: {metrics}")
