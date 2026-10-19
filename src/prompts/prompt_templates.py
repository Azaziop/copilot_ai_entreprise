"""Versioned prompt templates."""

from __future__ import annotations

PROMPTS: dict[str, dict[str, str]] = {
    "grounded_answer": {
        "v1": (
            "Tu es un assistant enterprise. Réponds uniquement à partir du contexte.\n"
            "Contexte:\n{context}\n\nQuestion: {question}\n\n"
            "Réponse avec citations:"
        ),
    },
}


def get_prompt(name: str, version: str = "v1") -> str:
    return PROMPTS[name][version]
