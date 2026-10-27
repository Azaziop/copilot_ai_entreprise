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
from src.retrieval.filename_scope import (
    doc_filename_from_meta,
    extract_named_filenames,
    filter_items_by_filenames,
    list_data_dir_filenames,
)
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

# Hybrid / BM25 corpus cache
_bm25_corpus: list[Document] = []
_bm25_index = None
_cross_encoder = None
_cross_encoder_failed = False

# Warm BM25 after vector store init (defined below, called at module end)


def _tokenize(text: str) -> list[str]:
    import re

    return re.findall(r"[a-zA-ZÀ-ÿ0-9]+", (text or "").lower())


def _refresh_bm25_corpus() -> None:
    """Rebuild BM25 from Chroma documents (dense + sparse hybrid)."""
    global _bm25_corpus, _bm25_index
    try:
        from rank_bm25 import BM25Okapi

        raw = vector_store.get(include=["documents", "metadatas"])
        docs_txt = raw.get("documents") or []
        metas = raw.get("metadatas") or []
        corpus: list[Document] = []
        for i, text in enumerate(docs_txt):
            if not text:
                continue
            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            corpus.append(Document(page_content=text, metadata=dict(meta)))
        if not corpus:
            _bm25_corpus = []
            _bm25_index = None
            return
        _bm25_corpus = corpus
        _bm25_index = BM25Okapi([_tokenize(d.page_content) for d in corpus])
    except Exception:
        _bm25_corpus = []
        _bm25_index = None


def _bm25_search(question: str, top_k: int = 20) -> list[Document]:
    if _bm25_index is None or not _bm25_corpus:
        _refresh_bm25_corpus()
    if _bm25_index is None or not _bm25_corpus:
        return []
    scores = _bm25_index.get_scores(_tokenize(question))
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [_bm25_corpus[i] for i in ranked[:top_k] if scores[i] > 0]


def _doc_key(doc: Document) -> str:
    meta = doc.metadata or {}
    raw = meta.get("source") or meta.get("filename") or "document"
    page = meta.get("page")
    content_sig = (doc.page_content or "")[:120]
    return f"{Path(str(raw)).name}|{page}|{hash(content_sig)}"


def _rrf_fuse(
    rankings: list[list[Document]], k: int = 60, top_n: int = 15
) -> list[Document]:
    scores: dict[str, float] = {}
    by_key: dict[str, Document] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking):
            key = _doc_key(doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            by_key[key] = doc
    ordered = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)
    return [by_key[key] for key in ordered[:top_n]]


def _rerank(question: str, docs: list[Document], top_n: int = 5) -> list[Document]:
    """Cross-encoder rerank when available; else lexical overlap fallback."""
    global _cross_encoder, _cross_encoder_failed
    if not docs:
        return []

    use_ce = os.getenv("USE_CROSS_ENCODER", "1").lower() not in {"0", "false", "no"}
    if use_ce and not _cross_encoder_failed:
        try:
            if _cross_encoder is None:
                from sentence_transformers import CrossEncoder

                _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            pairs = [[question, d.page_content[:1500]] for d in docs]
            scores = _cross_encoder.predict(pairs)
            ranked = sorted(
                zip(docs, scores), key=lambda x: float(x[1]), reverse=True
            )
            return [d for d, _ in ranked[:top_n]]
        except Exception:
            _cross_encoder_failed = True

    q_tokens = set(_tokenize(question))
    scored = []
    for d in docs:
        d_tokens = set(_tokenize(d.page_content))
        overlap = len(q_tokens & d_tokens) / max(1, len(q_tokens))
        scored.append((overlap, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_n]]


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


def _doc_filename(doc: Document) -> str:
    return doc_filename_from_meta(doc.metadata)


def known_corpus_filenames() -> set[str]:
    """Filenames present in the vector/BM25 corpus or data/raw."""
    names: set[str] = set()
    if not _bm25_corpus:
        try:
            _refresh_bm25_corpus()
        except Exception:
            pass
    for d in _bm25_corpus:
        names.add(_doc_filename(d))
    if not names:
        try:
            raw = vector_store.get(include=["metadatas"])
            for meta in raw.get("metadatas") or []:
                if not isinstance(meta, dict):
                    continue
                raw_s = meta.get("source") or meta.get("filename")
                if raw_s:
                    names.add(Path(str(raw_s)).name)
        except Exception:
            pass
    names |= list_data_dir_filenames("data/raw", "data")
    return names


def named_files_in_question(question: str) -> list[str]:
    """Detect files named in the question against the live corpus."""
    return extract_named_filenames(question, known=known_corpus_filenames())


def _filter_docs_by_filenames(
    docs: list[Document], filenames: list[str]
) -> list[Document]:
    return filter_items_by_filenames(
        docs, filenames, filename_of=_doc_filename
    )


def _docs_for_filenames(filenames: list[str], limit: int = 80) -> list[Document]:
    """Fallback: all chunks belonging to the named files."""
    want = {f.lower() for f in filenames}
    if not _bm25_corpus:
        _refresh_bm25_corpus()
    out: list[Document] = []
    for d in _bm25_corpus:
        if _doc_filename(d).lower() in want:
            out.append(d)
            if len(out) >= limit:
                break
    return out


def retrieve_with_sources(question: str, k: int = 5):
    """Hybrid dense+BM25 (RRF) → rerank → dedupe by page. Returns (docs, sources).

    If the question names one or more corpus files (e.g. « d'après CV - X.pdf »),
    retrieval is scoped to those files only so unrelated PDFs never appear as sources.
    """
    named = extract_named_filenames(question, known=known_corpus_filenames())
    fetch_k = max(20, k * 4)
    # Over-fetch when scoping so post-filter still has enough candidates
    search_k = fetch_k * 3 if named else fetch_k

    dense = vector_store.similarity_search(question, k=search_k)
    sparse = _bm25_search(question, top_k=search_k)
    if named:
        dense = _filter_docs_by_filenames(dense, named)
        sparse = _filter_docs_by_filenames(sparse, named)
        if not dense and not sparse:
            dense = _docs_for_filenames(named)

    fused = _rrf_fuse([dense, sparse], top_n=15) if sparse else dense[:15]
    if not fused:
        fused = dense or (_docs_for_filenames(named) if named else [])
    reranked = _rerank(question, fused, top_n=max(k, 5))

    deduped_docs = []
    seen_pages = set()
    for doc in reranked:
        meta = dict(doc.metadata or {})
        filename = _doc_filename(doc)
        key = _page_key(meta, filename)
        if key in seen_pages:
            continue
        seen_pages.add(key)
        deduped_docs.append(doc)
        if len(deduped_docs) >= k:
            break

    sources = [_source_from_doc(d) for d in deduped_docs]
    return deduped_docs, sources


def select_cited_sources(
    answer: str,
    sources: list[dict],
    max_n: int = 2,
    allowed_filenames: list[str] | None = None,
) -> list[dict]:
    """Keep supporting passages, then collapse to one card per filename."""
    import re

    if not answer or not sources:
        return []

    if allowed_filenames:
        allow = {f.lower() for f in allowed_filenames}
        sources = [
            s for s in sources if (s.get("filename") or "").lower() in allow
        ]
        if not sources:
            return []
        max_n = min(max_n, max(1, len(allowed_filenames)))

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


try:
    _refresh_bm25_corpus()
except Exception:
    pass
