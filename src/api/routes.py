"""FastAPI routes — serving only (indexing is offline)."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from src.pipelines.query_pipeline import run_query_pipeline


class QueryRequest(BaseModel):
    question: str
    user_roles: list[str] | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[str]


def create_app() -> FastAPI:
    app = FastAPI(title="Enterprise Copilot RAG", version="0.1.0")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/query", response_model=QueryResponse)
    def query(body: QueryRequest):
        result = run_query_pipeline(body.question, user_roles=body.user_roles)
        return QueryResponse(answer=result.answer, citations=result.citations)

    return app
