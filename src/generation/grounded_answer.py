"""Grounded answer generation with citations."""

from __future__ import annotations

from src.llm.llm_client import LLMClient
from src.prompts.prompt_templates import get_prompt
from src.schemas.models import Chunk, QueryResult


def generate_grounded_answer(
    query: str,
    chunks: list[Chunk],
    llm: LLMClient | None = None,
) -> QueryResult:
    llm = llm or LLMClient()
    context = "\n\n".join(
        f"[{i + 1}] {c.content}" for i, c in enumerate(chunks)
    )
    prompt = get_prompt("grounded_answer").format(context=context, question=query)
    answer = llm.generate(prompt) if chunks else "Aucun contexte pertinent trouvé."
    citations = [
        c.metadata.get("source") or c.document_id for c in chunks if c.content
    ]
    return QueryResult(
        query=query,
        answer=answer,
        chunks=chunks,
        citations=citations,
    )
