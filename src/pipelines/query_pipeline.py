"""Online query pipeline: rewrite → retrieve → rerank → generate."""

from __future__ import annotations

import yaml

from src.cache.semantic_cache import SemanticCache
from src.embeddings.embedder import Embedder
from src.generation.grounded_answer import generate_grounded_answer
from src.lexical.bm25_index import BM25Index
from src.llm.llm_client import LLMClient
from src.observability.tracing import get_tracer, span
from src.query.query import rewrite_query, route_query
from src.rerank.reranker import Reranker
from src.retrieval.retriever import HybridRetriever
from src.schemas.models import QueryResult
from src.security.acl import filter_chunks_by_acl
from src.vector_db.store import VectorStore


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_query_pipeline(
    question: str,
    user_roles: list[str] | None = None,
    config_path: str = "config.yaml",
) -> QueryResult:
    config = load_config(config_path)
    tracer = get_tracer("query_pipeline")
    cache = SemanticCache(
        redis_url=config["cache"].get("redis_url"),
        ttl_seconds=config["cache"].get("ttl_seconds", 3600),
    )

    cached = cache.get_exact(question)
    if cached is not None:
        return cached

    with span("rewrite", tracer):
        q = rewrite_query(question)
        _ = route_query(q)

    embedder = Embedder(config["models"]["embedding"])
    retriever = HybridRetriever(
        vector_store=VectorStore(
            persist_directory=config["vector_db"]["persist_directory"],
            collection=config["vector_db"]["collection"],
        ),
        lexical_index=BM25Index(),
        embedder=embedder,
        rrf_k=config["retrieval"]["rrf_k"],
    )

    with span("retrieve", tracer):
        chunks = retriever.retrieve(q, top_k=config["retrieval"]["top_k"])

    with span("acl", tracer):
        chunks = filter_chunks_by_acl(chunks, user_roles=user_roles)

    if config["rerank"]["enabled"]:
        with span("rerank", tracer):
            chunks = Reranker(config["models"]["reranker"]).rerank(
                q, chunks, top_n=config["rerank"]["top_n"]
            )

    with span("generate", tracer):
        llm = LLMClient(
            model=config["models"]["llm"],
            base_url=config["models"]["llm_base_url"],
        )
        result = generate_grounded_answer(q, chunks, llm=llm)

    cache.set_exact(question, result)
    return result
