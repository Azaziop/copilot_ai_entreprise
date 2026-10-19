"""Tracing, latency, and cost monitoring."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def setup_logging(log_path: str = "logs/app.log", level: str = "INFO") -> None:
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def get_tracer(name: str = "rag"):
    return logging.getLogger(name)


def log_event(tracer, event: str, **fields: Any) -> None:
    tracer.info("%s %s", event, fields)


@contextmanager
def span(name: str, tracer=None) -> Iterator[dict[str, Any]]:
    tracer = tracer or get_tracer()
    start = time.perf_counter()
    meta: dict[str, Any] = {"name": name}
    try:
        yield meta
    finally:
        meta["latency_ms"] = (time.perf_counter() - start) * 1000
        log_event(tracer, "span", **meta)
