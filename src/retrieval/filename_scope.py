"""Scope retrieval to filenames explicitly named in the user question."""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Iterable


_DASHES = {
    "\u2010",
    "\u2011",
    "\u2012",
    "\u2013",
    "\u2014",
    "\u2212",
    "\uFE58",
    "\uFE63",
    "\uFF0D",
}


def normalize_text(value: str) -> str:
    """Fold unicode dashes/spaces so filename matching is reliable."""
    if not value:
        return ""
    text = unicodedata.normalize("NFKC", value)
    for dash in _DASHES:
        text = text.replace(dash, "-")
    text = text.replace("\u00a0", " ")
    return text


def doc_filename_from_meta(meta: dict | None) -> str:
    meta = meta or {}
    raw = meta.get("source") or meta.get("filename") or "document"
    return Path(str(raw)).name


def extract_named_filenames(
    question: str, known: Iterable[str] | None = None
) -> list[str]:
    """Detect corpus files explicitly referenced in the user question."""
    if not question or not question.strip():
        return []

    corpus = set(known or ())
    q_norm = normalize_text(question)
    q_lower = q_norm.lower()
    found: list[str] = []

    # Longest names first so "CV - ZAOUI ANASS.pdf" wins over shorter stems
    for name in sorted(corpus, key=len, reverse=True):
        name_norm = normalize_text(name)
        name_l = name_norm.lower()
        if name_l and name_l in q_lower:
            found.append(name)
            continue
        stem = Path(name_norm).stem
        if len(stem) >= 8 and stem.lower() in q_lower:
            found.append(name)

    for m in re.finditer(
        r"[\w\- .()&]+\.(?:pdf|csv|xlsx?|txt|md)",
        q_norm,
        flags=re.IGNORECASE,
    ):
        cand = m.group(0).strip(" :;,")
        match = next(
            (
                n
                for n in corpus
                if normalize_text(n).lower() == normalize_text(cand).lower()
            ),
            None,
        )
        if match:
            if match not in found:
                found.append(match)
        elif cand and normalize_text(cand).lower() not in {
            normalize_text(f).lower() for f in found
        }:
            found.append(cand)

    out: list[str] = []
    seen: set[str] = set()
    for name in found:
        key = normalize_text(name).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def filenames_mentioned_in_question(
    question: str, filenames: Iterable[str]
) -> list[str]:
    """Return filenames (from candidates) whose basename appears in the question."""
    q_lower = normalize_text(question).lower()
    mentioned: list[str] = []
    seen: set[str] = set()
    for name in sorted({f for f in filenames if f}, key=len, reverse=True):
        key = normalize_text(name).lower()
        if not key or key in seen:
            continue
        if key in q_lower or (len(Path(name).stem) >= 8 and Path(name).stem.lower() in q_lower):
            mentioned.append(name)
            seen.add(key)
    return mentioned


def filter_sources_to_question(
    question: str, sources: list[dict]
) -> list[dict]:
    """Hard filter: if the question names any source file, keep only those."""
    if not sources:
        return []
    names = [str(s.get("filename") or "") for s in sources]
    mentioned = filenames_mentioned_in_question(question, names)
    if not mentioned:
        # Also accept explicit extract even if not yet in sources list
        mentioned = extract_named_filenames(question, known=set(names))
    if not mentioned:
        return sources
    allow = {normalize_text(n).lower() for n in mentioned}
    return [
        s
        for s in sources
        if normalize_text(str(s.get("filename") or "")).lower() in allow
    ]


def filter_items_by_filenames(
    items: list,
    filenames: list[str],
    *,
    filename_of,
) -> list:
    want = {normalize_text(f).lower() for f in filenames}
    return [
        item
        for item in items
        if normalize_text(filename_of(item)).lower() in want
    ]


def list_data_dir_filenames(*dirs: str) -> set[str]:
    names: set[str] = set()
    for data_dir in dirs:
        if not os.path.isdir(data_dir):
            continue
        for f in os.listdir(data_dir):
            if os.path.isfile(os.path.join(data_dir, f)):
                names.add(f)
    return names
