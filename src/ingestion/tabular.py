"""Load CSV / XLSX into LangChain Documents for RAG."""

from __future__ import annotations

from pathlib import Path

from langchain_core.documents import Document


def _dataframe_to_docs(
    df,
    *,
    source: str,
    sheet_name: str | None = None,
    rows_per_chunk: int = 40,
) -> list[Document]:
    if df is None or df.empty:
        return []

    # Normalize headers / cells to strings
    df = df.fillna("").astype(str)
    columns = [str(c).strip() for c in df.columns.tolist()]
    header = " | ".join(columns)
    prefix = f"Fichier: {Path(source).name}"
    if sheet_name:
        prefix += f" | Feuille: {sheet_name}"

    docs: list[Document] = []
    total = len(df)
    for start in range(0, total, rows_per_chunk):
        end = min(start + rows_per_chunk, total)
        lines = [prefix, header]
        for _, row in df.iloc[start:end].iterrows():
            lines.append(" | ".join(str(row[c]) for c in df.columns))
        docs.append(
            Document(
                page_content="\n".join(lines),
                metadata={
                    "source": source,
                    "sheet": sheet_name or "",
                    "row_start": start + 1,
                    "row_end": end,
                    "type": Path(source).suffix.lstrip(".").lower(),
                },
            )
        )
    return docs


def load_tabular_documents(file_path: str | Path) -> list[Document]:
    """Parse .csv / .xlsx / .xls into chunked text documents."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    source = str(path)

    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "pandas est requis pour CSV/XLSX. Installez: pip install pandas openpyxl"
        ) from exc

    if suffix == ".csv":
        # utf-8-sig handles Excel-exported CSV with BOM
        try:
            df = pd.read_csv(path, encoding="utf-8-sig")
        except UnicodeDecodeError:
            df = pd.read_csv(path, encoding="latin-1")
        return _dataframe_to_docs(df, source=source)

    if suffix in {".xlsx", ".xls"}:
        engine = "openpyxl" if suffix == ".xlsx" else None
        sheets = pd.read_excel(path, sheet_name=None, engine=engine)
        docs: list[Document] = []
        for name, df in sheets.items():
            docs.extend(_dataframe_to_docs(df, source=source, sheet_name=str(name)))
        return docs

    return []
