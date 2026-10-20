"""Streaming orchestration for Enterprise Copilot (reasoning + tokens + sources)."""

from __future__ import annotations

import os
from typing import Any, Iterator

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from agents import call_mcp_tool, structured_router
from rag import format_docs_for_prompt, retrieve_with_sources

load_dotenv(override=True)


def _llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        model="deepseek/deepseek-chat",
        temperature=0,
        streaming=True,
    )


def _route(question: str) -> str:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "Tu es un routeur d'entreprise expert. "
                    "Détermine la destination de la requête selon le schéma fourni. "
                    "Toute question sur le contenu d'un document (PDF, CV, bilan, IFRS, "
                    "capitaux propres, politiques RH) doit aller vers RAG."
                ),
            ),
            ("human", "{question}"),
        ]
    )
    result = (prompt | structured_router).invoke({"question": question})
    return result.destination


def _source_payload(docs_meta: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return docs_meta


def stream_chat(question: str) -> Iterator[dict[str, Any]]:
    """Yield SSE event payloads (sync generator; FastAPI wraps as StreamingResponse)."""
    yield {"type": "reasoning", "text": "Réception de la question et préparation du pipeline agent…"}
    yield {"type": "reasoning", "text": "Étape 1/3 — Routage (RAG / TOOL / DIRECT)…"}

    decision = _route(question)
    yield {
        "type": "reasoning",
        "text": f"Route sélectionnée : **{decision}**.",
    }
    yield {"type": "route", "route": decision}

    llm = _llm()
    answer_parts: list[str] = []

    if decision == "RAG":
        yield {
            "type": "reasoning",
            "text": "Étape 2/3 — Recherche vectorielle dans le corpus indexé…",
        }
        docs, sources = retrieve_with_sources(question)
        yield {
            "type": "reasoning",
            "text": f"{len(docs)} passage(s) pertinent(s) récupéré(s).",
        }
        yield {"type": "sources", "sources": _source_payload(sources)}

        if sources:
            listed = ", ".join(
                f"{s['filename']} ({s['location']})" for s in sources[:5]
            )
            yield {
                "type": "reasoning",
                "text": f"Sources retenues : {listed}.",
            }
        else:
            yield {
                "type": "reasoning",
                "text": "Aucun passage trouvé — la réponse indiquera l’absence de contexte.",
            }

        yield {
            "type": "reasoning",
            "text": "Étape 3/3 — Génération grounded (stream) à partir du contexte…",
        }

        template = """Tu es un analyste documentaire senior. Réponds UNIQUEMENT à partir du contexte.
Si le contexte contient des chiffres, cite-les avec l'unité et l'année.
Si l'information n'est pas dans le contexte, dis-le clairement sans inventer.
Réponds en markdown structuré.

Contexte:
{context}

Question: {input}"""
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | llm | StrOutputParser()
        context = format_docs_for_prompt(docs)
        for chunk in chain.stream({"context": context, "input": question}):
            if not chunk:
                continue
            answer_parts.append(chunk)
            yield {"type": "token", "text": chunk}

    elif decision == "TOOL":
        yield {
            "type": "sources",
            "sources": [
                {
                    "type": "tool",
                    "filename": "MCP tools",
                    "location": "serveur MCP local",
                    "lines": None,
                    "label": "Outils MCP (statut, documents, analytics…)",
                }
            ],
        }
        yield {
            "type": "reasoning",
            "text": "Étape 2/3 — Appel des outils MCP…",
        }
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            tool_text = loop.run_until_complete(call_mcp_tool(question))
        finally:
            loop.close()

        yield {
            "type": "reasoning",
            "text": "Étape 3/3 — Synthèse de la sortie outil…",
        }
        # Stream tool result in small chunks for UI parity
        for i in range(0, len(tool_text), 24):
            piece = tool_text[i : i + 24]
            answer_parts.append(piece)
            yield {"type": "token", "text": piece}

    else:  # DIRECT
        yield {
            "type": "sources",
            "sources": [
                {
                    "type": "direct",
                    "filename": "Modèle LLM",
                    "location": "connaissances générales (sans corpus)",
                    "lines": None,
                    "label": "Réponse directe — pas de document indexé",
                }
            ],
        }
        yield {
            "type": "reasoning",
            "text": "Étape 2/3 — Pas de retrieval ; génération directe…",
        }
        yield {
            "type": "reasoning",
            "text": "Étape 3/3 — Stream de la réponse assistant…",
        }
        prompt = ChatPromptTemplate.from_template(
            "Tu es un assistant d'entreprise professionnel, clair et concis. "
            "Réponds en français, en markdown si utile.\n\nQuestion : {question}"
        )
        chain = prompt | llm | StrOutputParser()
        for chunk in chain.stream({"question": question}):
            if not chunk:
                continue
            answer_parts.append(chunk)
            yield {"type": "token", "text": chunk}

    full = "".join(answer_parts).strip()
    yield {"type": "done", "answer": full, "route": decision}
