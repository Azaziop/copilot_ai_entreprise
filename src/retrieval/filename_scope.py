"""Scope retrieval to filenames explicitly named in the user question."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


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
    q_lower = question.lower()
    found: list[str] = []

    # Longest names first so "CV - ZAOUI ANASS.pdf" wins over shorter stems
    for name in sorted(corpus, key=len, reverse=True):
        name_l = name.lower()
        if name_l in q_lower:
            found.append(name)
            continue
        stem = Path(name).stem
        if len(stem) >= 8 and stem.lower() in q_lower:
            found.append(name)

    for m in re.finditer(
        r"[\w\- .()&]+\.(?:pdf|csv|xlsx?|txt|md)", question, flags=re.IGNORECASE
    ):
        cand = m.group(0).strip(" :;,")
        match = next((n for n in corpus if n.lower() == cand.lower()), None)
        if match:
            if match not in found:
                found.append(match)
        elif cand and cand.lower() not in {f.lower() for f in found}:
            found.append(cand)

    out: list[str] = []
    seen: set[str] = set()
    for name in found:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def filter_items_by_filenames(
    items: list,
    filenames: list[str],
    *,
    filename_of,
) -> list:
    want = {f.lower() for f in filenames}
    return [item for item in items if filename_of(item).lower() in want]


def list_data_dir_filenames(*dirs: str) -> set[str]:
    names: set[str] = set()
    for data_dir in dirs:
        if not os.path.isdir(data_dir):
            continue
        for f in os.listdir(data_dir):
            if os.path.isfile(os.path.join(data_dir, f)):
                names.add(f)
    return names
