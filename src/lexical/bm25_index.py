"""BM25 / keyword index for hybrid search."""

from __future__ import annotations

import re

from src.schemas.models import Chunk


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ0-9]+", (text or "").lower())


class BM25Index:
    def __init__(self):
        self._chunks: list[Chunk] = []
        self._index = None

    def build(self, chunks: list[Chunk]) -> None:
        self._chunks = list(chunks)
        try:
            from rank_bm25 import BM25Okapi

            self._index = BM25Okapi([_tokenize(c.content) for c in self._chunks])
        except Exception:
            self._index = None

    def search(self, query: str, top_k: int = 10) -> list[Chunk]:
        if not self._chunks:
            return []
        if self._index is None:
            return self._chunks[:top_k]
        scores = self._index.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out = []
        for i in ranked:
            if scores[i] <= 0:
                break
            out.append(self._chunks[i])
            if len(out) >= top_k:
                break
        return out
