"""Cross-encoder reranking (with lexical fallback)."""

from __future__ import annotations

import os
import re

from src.schemas.models import Chunk


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ÿ0-9]+", (text or "").lower())


class Reranker:
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self._model = None
        self._failed = False

    def _get_model(self):
        if self._failed:
            return None
        if self._model is not None:
            return self._model
        if os.getenv("USE_CROSS_ENCODER", "1").lower() in {"0", "false", "no"}:
            self._failed = True
            return None
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            return self._model
        except Exception:
            self._failed = True
            return None

    def rerank(self, query: str, chunks: list[Chunk], top_n: int = 5) -> list[Chunk]:
        if not chunks:
            return []
        model = self._get_model()
        if model is not None:
            pairs = [[query, c.content[:1500]] for c in chunks]
            scores = model.predict(pairs)
            ranked = sorted(zip(chunks, scores), key=lambda x: float(x[1]), reverse=True)
            return [c for c, _ in ranked[:top_n]]

        q = set(_tokenize(query))
        scored = []
        for c in chunks:
            overlap = len(q & set(_tokenize(c.content))) / max(1, len(q))
            scored.append((overlap, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:top_n]]
