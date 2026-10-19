"""Connectors for loading documents from disk / remote sources."""

from __future__ import annotations

from pathlib import Path

from src.ingestion.parsers import parse_file
from src.schemas.models import Document


def load_documents(raw_dir: str | Path = "data/raw") -> list[Document]:
    """Load and parse all supported files under `raw_dir`."""
    root = Path(raw_dir)
    if not root.exists():
        return []

    documents: list[Document] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            documents.extend(parse_file(path))
    return documents
