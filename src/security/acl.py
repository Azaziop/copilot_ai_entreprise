"""Auth and chunk-level Access Control Lists."""

from __future__ import annotations

from src.schemas.models import Chunk


def filter_chunks_by_acl(
    chunks: list[Chunk],
    user_roles: list[str] | None = None,
) -> list[Chunk]:
    """Drop chunks the caller is not allowed to see."""
    if not user_roles:
        return chunks
    allowed: list[Chunk] = []
    for chunk in chunks:
        acl = chunk.metadata.get("acl") or chunk.metadata.get("roles")
        if acl is None or set(acl) & set(user_roles):
            allowed.append(chunk)
    return allowed
