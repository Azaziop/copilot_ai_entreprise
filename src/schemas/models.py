"""Pydantic models: Document, Chunk, QueryResult."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Document(BaseModel):
    id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None


class Chunk(BaseModel):
    id: str
    document_id: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None


class QueryResult(BaseModel):
    query: str
    answer: str
    chunks: list[Chunk] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
