"""Chunking strategies: recursive, parent-child, token limits."""

from __future__ import annotations

from uuid import uuid4

from src.schemas.models import Chunk, Document


def chunk_documents(
    documents: list[Document],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Chunk]:
    """Split documents into overlapping text chunks."""
    chunks: list[Chunk] = []
    for doc in documents:
        text = doc.content or ""
        if not text:
            continue
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            piece = text[start:end]
            chunks.append(
                Chunk(
                    id=str(uuid4()),
                    document_id=doc.id,
                    content=piece,
                    metadata={**doc.metadata, "source": doc.source},
                )
            )
            if end >= len(text):
                break
            start = max(0, end - chunk_overlap)
    return chunks
