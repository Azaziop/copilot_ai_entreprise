"""Unit / integration tests and retrieval regression checks."""

from src.retrieval.retriever import reciprocal_rank_fusion
from src.schemas.models import Chunk


def test_rrf_merges_rankings():
    a = Chunk(id="a", document_id="d1", content="alpha")
    b = Chunk(id="b", document_id="d2", content="beta")
    c = Chunk(id="c", document_id="d3", content="gamma")

    fused = reciprocal_rank_fusion([[a, b], [b, c]])
    assert fused[0].id == "b"
    assert {x.id for x in fused} == {"a", "b", "c"}


def test_chunk_model():
    chunk = Chunk(id="1", document_id="doc", content="hello")
    assert chunk.content == "hello"
