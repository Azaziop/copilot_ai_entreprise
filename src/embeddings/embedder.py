"""Embed chunks and track embedding model version."""

from __future__ import annotations

from src.schemas.models import Chunk


class Embedder:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.version = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from langchain_huggingface import HuggingFaceEmbeddings

            self._model = HuggingFaceEmbeddings(model_name=self.model_name)
        return self._model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_model()
        return model.embed_documents(texts)

    def embed_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        vectors = self.embed_texts([c.content for c in chunks])
        for chunk, vector in zip(chunks, vectors):
            chunk.embedding = vector
            chunk.metadata["embedding_model"] = self.version
        return chunks
