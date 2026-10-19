"""Application entry point — exposes the real FastAPI app (app.py)."""

from __future__ import annotations

import uvicorn

# Réutilise l'API Enterprise Copilot (/chat, /upload, …)
from app import app  # noqa: F401

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
