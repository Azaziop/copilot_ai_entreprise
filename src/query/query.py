"""Query rewriting, routing, and HyDE."""

from __future__ import annotations


def rewrite_query(query: str) -> str:
    """Normalize / expand the user query before retrieval."""
    return query.strip()


def route_query(query: str) -> str:
    """Route to a retrieval strategy: hybrid | lexical | dense | hyde."""
    _ = query
    return "hybrid"


def hyde_query(query: str) -> str:
    """Hypothetical document embedding (HyDE) placeholder."""
    return query
