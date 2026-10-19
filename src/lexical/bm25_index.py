"""BM25 / keyword index for hybrid search."""

from __future__ import annotations

from src.schemas.models import Chunk


class BM25Index:
    def __init__(self):
        self._chunks: list[Chunk] = []
        self._index = None

    def build(self, chunks: list[Chunk]) -> None:
        self._chunks = chunks
        # Hook: rank_bm25.BM25Okapi([c.content.split() for c in chunks])

    def search(self, query: str, top_k: int = 10) -> list[Chunk]:
        _ = (query, top_k)
        return self._chunks[:top_k]
