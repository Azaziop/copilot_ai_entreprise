"""Job: index / reindex the document corpus."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.observability.tracing import setup_logging
from src.pipelines.index_pipeline import run_index_pipeline


if __name__ == "__main__":
    setup_logging()
    stats = run_index_pipeline()
    print(f"Indexing complete: {stats}")
