"""Unit / integration tests and retrieval regression checks."""

from src.retrieval.filename_scope import (
    doc_filename_from_meta,
    extract_named_filenames,
    filter_items_by_filenames,
    filter_sources_to_question,
)
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


def test_extract_named_filenames_scopes_to_cv():
    known = {
        "CV - ZAOUI ANASS.pdf",
        "COMPTES OCP IFRS_CONSO & SOCIAUX_vFR.pdf",
        "sample_ventes.csv",
    }
    q = (
        "donnez moi le profile et les compétences de ce fichier:"
        "CV - ZAOUI ANASS.pdf"
    )
    found = extract_named_filenames(q, known=known)
    assert found == ["CV - ZAOUI ANASS.pdf"]


def test_filter_sources_to_question_drops_ocp():
    q = "donnez moi le profile de ce fichier:CV - ZAOUI ANASS.pdf"
    sources = [
        {"filename": "CV - ZAOUI ANASS.pdf", "location": "page 1"},
        {
            "filename": "COMPTES OCP IFRS_CONSO & SOCIAUX_vFR.pdf",
            "location": "page 34",
        },
    ]
    filtered = filter_sources_to_question(q, sources)
    assert len(filtered) == 1
    assert filtered[0]["filename"] == "CV - ZAOUI ANASS.pdf"


def test_filter_items_by_filenames_drops_other_pdfs():
    items = [
        {"source": "data/raw/CV - ZAOUI ANASS.pdf"},
        {"source": "data/raw/COMPTES OCP IFRS_CONSO & SOCIAUX_vFR.pdf"},
    ]
    filtered = filter_items_by_filenames(
        items,
        ["CV - ZAOUI ANASS.pdf"],
        filename_of=lambda item: doc_filename_from_meta(item),
    )
    assert len(filtered) == 1
    assert "CV" in filtered[0]["source"]
