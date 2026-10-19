"""Offline indexing pipeline: load → parse → chunk → embed → index."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.chunking.chunker import chunk_documents
from src.embeddings.embedder import Embedder
from src.ingestion.loader import load_documents
from src.lexical.bm25_index import BM25Index
from src.observability.tracing import get_tracer, log_event, span
from src.vector_db.store import VectorStore


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_index_pipeline(config_path: str = "config.yaml") -> dict:
    config = load_config(config_path)
    tracer = get_tracer("index_pipeline")

    with span("load", tracer):
        docs = load_documents("data/raw")

    with span("chunk", tracer):
        chunks = chunk_documents(
            docs,
            chunk_size=config["chunking"]["chunk_size"],
            chunk_overlap=config["chunking"]["chunk_overlap"],
        )

    with span("embed", tracer):
        embedder = Embedder(config["models"]["embedding"])
        chunks = embedder.embed_chunks(chunks)

    with span("vector_upsert", tracer):
        store = VectorStore(
            persist_directory=config["vector_db"]["persist_directory"],
            collection=config["vector_db"]["collection"],
        )
        n = store.upsert(chunks)

    with span("bm25_build", tracer):
        bm25 = BM25Index()
        bm25.build(chunks)
        Path("data/parsed").mkdir(parents=True, exist_ok=True)

    stats = {"documents": len(docs), "chunks": len(chunks), "upserted": n}
    log_event(tracer, "index_complete", **stats)
    return stats
