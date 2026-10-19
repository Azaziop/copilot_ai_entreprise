"""Hybrid search, metadata filters, and RRF fusion."""

from __future__ import annotations

from typing import Any

from src.embeddings.embedder import Embedder
from src.lexical.bm25_index import BM25Index
from src.schemas.models import Chunk
from src.vector_db.store import VectorStore


def reciprocal_rank_fusion(
    rankings: list[list[Chunk]],
    k: int = 60,
) -> list[Chunk]:
    scores: dict[str, float] = {}
    by_id: dict[str, Chunk] = {}
    for ranking in rankings:
        for rank, chunk in enumerate(ranking):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank + 1)
            by_id[chunk.id] = chunk
    ordered = sorted(scores, key=scores.get, reverse=True)
    return [by_id[i] for i in ordered]


class HybridRetriever:
    def __init__(
        self,
        vector_store: VectorStore,
        lexical_index: BM25Index,
        embedder: Embedder,
        rrf_k: int = 60,
    ):
        self.vector_store = vector_store
        self.lexical_index = lexical_index
        self.embedder = embedder
        self.rrf_k = rrf_k

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[Chunk]:
        query_vec = self.embedder.embed_texts([query])[0]
        dense = self.vector_store.search(query_vec, top_k=top_k, filters=filters)
        sparse = self.lexical_index.search(query, top_k=top_k)
        fused = reciprocal_rank_fusion([dense, sparse], k=self.rrf_k)
        return fused[:top_k]
