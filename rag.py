import os
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain_core.documents import Document
from src.ingestion.tabular import load_tabular_documents
from dotenv import load_dotenv

load_dotenv(override=True)


def init_rag():
    docs = []
    data_dirs = ["data/raw", "data"]
    for data_dir in data_dirs:
        if not os.path.isdir(data_dir):
            continue
        for file in os.listdir(data_dir):
            file_path = os.path.join(data_dir, file)
            if not os.path.isfile(file_path):
                continue
            lower = file.lower()
            if lower.endswith(".pdf"):
                docs.extend(PyPDFLoader(file_path).load())
            elif lower.endswith((".txt", ".md")):
                docs.extend(TextLoader(file_path, encoding="utf-8").load())
            elif lower.endswith((".csv", ".xlsx", ".xls")):
                docs.extend(load_tabular_documents(file_path))

    if not docs:
        docs = [Document(page_content="Bienvenue dans l'assistant Enterprise Copilot.")]

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=120)
    chunks = text_splitter.split_documents(docs)

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    persist_directory = "./chroma_db"

    # Réutilise l'index persistant s'il existe déjà (évite de tout écraser)
    if os.path.isdir(persist_directory) and os.listdir(persist_directory):
        vector_store = Chroma(
            embedding_function=embeddings,
            persist_directory=persist_directory,
        )
        if chunks:
            vector_store.add_documents(chunks)
        return vector_store

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_directory,
    )
    return vector_store


# Instance globale du Vector Store pour l'ajout dynamique
vector_store = init_rag()
retriever = vector_store.as_retriever(search_kwargs={"k": 10})


def _doc_location(meta: dict, line_count: int) -> str:
    if meta.get("row_start") is not None and meta.get("row_end") is not None:
        sheet = meta.get("sheet") or ""
        base = f"lignes {meta['row_start']}–{meta['row_end']}"
        return f"{base}" + (f", feuille {sheet}" if sheet else "")
    if meta.get("page") is not None:
        try:
            page = int(meta["page"]) + 1
        except (TypeError, ValueError):
            page = meta["page"]
        return f"page {page} · {line_count} ligne(s)"
    return f"{line_count} ligne(s)"


def _page_key(meta: dict, filename: str) -> tuple:
    if meta.get("page") is not None:
        return (filename, "page", meta.get("page"))
    if meta.get("row_start") is not None:
        return (filename, "rows", meta.get("row_start"), meta.get("row_end"), meta.get("sheet"))
    return (filename, "chunk", meta.get("start_index") or id(meta))


def _source_from_doc(doc) -> dict:
    meta = dict(doc.metadata or {})
    raw_source = meta.get("source") or meta.get("filename") or "document"
    filename = Path(str(raw_source)).name
    line_count = max(1, doc.page_content.count("\n") + 1)
    location = _doc_location(meta, line_count)
    return {
        "type": "rag",
        "filename": filename,
        "location": location,
        "lines": line_count,
        "page": meta.get("page"),
        "row_start": meta.get("row_start"),
        "row_end": meta.get("row_end"),
        "sheet": meta.get("sheet") or None,
        "label": f"{filename} — {location}",
        "snippet": doc.page_content[:220].replace("\n", " "),
        "_content": doc.page_content,
    }


def retrieve_with_sources(question: str, k: int = 8):
    """Return (documents, source dicts) — one passage per page/file location."""
    docs = retriever.invoke(question)
    if k and len(docs) > k:
        docs = docs[:k]

    deduped_docs = []
    seen_pages = set()
    for doc in docs:
        meta = dict(doc.metadata or {})
        raw_source = meta.get("source") or meta.get("filename") or "document"
        filename = Path(str(raw_source)).name
        key = _page_key(meta, filename)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        deduped_docs.append(doc)

    sources = [_source_from_doc(d) for d in deduped_docs]
    return deduped_docs, sources


def select_cited_sources(answer: str, sources: list[dict], max_n: int = 2) -> list[dict]:
    """Keep supporting passages, then collapse to one card per filename."""
    import re

    if not answer or not sources:
        return []

    answer_norm = answer.lower()
    nums = set(re.findall(r"\d[\d\s]*\d|\d+", answer.replace("\u00a0", " ")))
    nums = {re.sub(r"\s+", "", n) for n in nums if len(re.sub(r"\s+", "", n)) >= 2}

    tokens = {
        t
        for t in re.findall(r"[a-zàâäéèêëïîôùûüç]{5,}", answer_norm)
        if t
        not in {
            "selon",
            "dapres",
            "extrait",
            "millions",
            "dirhams",
            "groupe",
            "total",
            "capitaux",
            "propres",
        }
    }

    scored: list[tuple[float, dict]] = []
    for src in sources:
        content = (src.get("_content") or src.get("snippet") or "").lower()
        if not content:
            continue
        score = 0.0
        content_compact = re.sub(r"\s+", "", content)
        for n in nums:
            if n in content_compact:
                score += 2.5
        hits = sum(1 for t in tokens if t in content)
        score += min(hits, 6) * 0.4
        if score > 0:
            scored.append((score, src))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        scored = [(1.0, s) for s in sources[:1]]

    # One UI card per filename (aggregate cited pages)
    by_file: dict[str, dict] = {}
    for score, src in scored:
        fn = src.get("filename") or "document"
        page = src.get("page")
        try:
            page_disp = int(page) + 1 if page is not None else None
        except (TypeError, ValueError):
            page_disp = page

        if fn not in by_file:
            by_file[fn] = {
                "type": src.get("type") or "rag",
                "filename": fn,
                "pages": [],
                "locations": [],
                "lines": src.get("lines"),
                "label": fn,
                "_score": score,
            }
        entry = by_file[fn]
        entry["_score"] = max(entry["_score"], score)
        if page_disp is not None and page_disp not in entry["pages"] and len(entry["pages"]) < 3:
            entry["pages"].append(page_disp)
        loc = src.get("location")
        if loc and loc not in entry["locations"] and len(entry["locations"]) < 3:
            entry["locations"].append(loc)

    ordered = sorted(by_file.values(), key=lambda e: e["_score"], reverse=True)[:max_n]
    result = []
    for entry in ordered:
        pages = entry.pop("pages", [])
        locs = entry.pop("locations", [])
        entry.pop("_score", None)
        if pages:
            pages_sorted = sorted(pages)
            entry["location"] = (
                f"page {pages_sorted[0]}"
                if len(pages_sorted) == 1
                else f"pages {', '.join(str(p) for p in pages_sorted)}"
            )
        elif locs:
            # strip verbose line counts → keep "page N" if present
            simplified = []
            for loc in locs:
                m = re.search(r"page\s+(\d+)", loc)
                simplified.append(f"page {m.group(1)}" if m else loc)
            entry["location"] = ", ".join(dict.fromkeys(simplified))
        else:
            entry["location"] = "document indexé"
        result.append(entry)
    return result


def format_docs_for_prompt(docs) -> str:
    parts = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata or {}
        raw_source = meta.get("source") or meta.get("filename") or "document"
        filename = Path(str(raw_source)).name
        line_count = max(1, doc.page_content.count("\n") + 1)
        loc = _doc_location(meta, line_count)
        parts.append(f"[Passage {i} | {filename} | {loc}]\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def get_rag_chain():
    llm = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        model="deepseek/deepseek-chat",
        temperature=0,
    )

    template = """Tu es un analyste documentaire senior. Réponds UNIQUEMENT à partir du contexte.
Si le contexte contient des chiffres (capitaux propres, bilan, IFRS, années), cite-les explicitement avec l'unité et l'année.
Si l'information n'est pas dans le contexte, dis-le clairement sans inventer.
Réponds en markdown structuré (titres, listes, tableaux si utile).

Contexte:
{context}

Question: {input}"""
    prompt = ChatPromptTemplate.from_template(template)

    rag_chain = (
        {
            "context": retriever | format_docs_for_prompt,
            "input": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )
    return rag_chain
