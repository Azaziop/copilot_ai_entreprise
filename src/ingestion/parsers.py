"""Parsers for PDF, HTML, text, and OCR-ready images."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from src.schemas.models import Document


SUPPORTED_TEXT = {".txt", ".md", ".html", ".htm"}
SUPPORTED_PDF = {".pdf"}
SUPPORTED_TABULAR = {".csv", ".xlsx", ".xls"}


def parse_file(path: str | Path) -> list[Document]:
    """Parse a single file into one or more Document objects."""
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix in SUPPORTED_TEXT:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return [
            Document(
                id=str(uuid4()),
                content=content,
                source=str(path),
                metadata={"filename": path.name, "type": suffix.lstrip(".")},
            )
        ]

    if suffix in SUPPORTED_PDF:
        # Hook for PDF / OCR loaders (e.g. PyPDFLoader, unstructured)
        return [
            Document(
                id=str(uuid4()),
                content="",
                source=str(path),
                metadata={"filename": path.name, "type": "pdf", "parsed": False},
            )
        ]

    if suffix in SUPPORTED_TABULAR:
        from src.ingestion.tabular import load_tabular_documents

        loaded = load_tabular_documents(path)
        return [
            Document(
                id=str(uuid4()),
                content=d.page_content,
                source=str(path),
                metadata={
                    "filename": path.name,
                    "type": suffix.lstrip("."),
                    **(d.metadata or {}),
                },
            )
            for d in loaded
        ]

    return []
