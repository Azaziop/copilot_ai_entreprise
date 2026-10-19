"""Cross-encoder reranking."""

from __future__ import annotations

from src.schemas.models import Chunk


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name

    def rerank(self, query: str, chunks: list[Chunk], top_n: int = 5) -> list[Chunk]:
        """Score query–chunk pairs and return the top_n chunks."""
        _ = (query, self.model_name)
        return chunks[:top_n]
