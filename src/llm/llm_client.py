"""LLM client with retries and fallbacks."""

from __future__ import annotations

import os
import time


class LLMClient:
    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        base_url: str = "https://openrouter.ai/api/v1",
        max_retries: int = 3,
        fallback_model: str | None = None,
    ):
        self.model = model
        self.base_url = base_url
        self.max_retries = max_retries
        self.fallback_model = fallback_model
        self._llm = None

    def _build(self, model: str):
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENROUTER_API_KEY")
        return ChatOpenAI(
            base_url=self.base_url,
            api_key=api_key,
            openai_api_key=api_key,
            model=model,
            temperature=0,
        )

    def generate(self, prompt: str) -> str:
        last_error: Exception | None = None
        models = [self.model]
        if self.fallback_model:
            models.append(self.fallback_model)

        for model in models:
            for attempt in range(self.max_retries):
                try:
                    llm = self._build(model)
                    return llm.invoke(prompt).content
                except Exception as exc:  # noqa: BLE001 — retry boundary
                    last_error = exc
                    time.sleep(2**attempt)
        raise RuntimeError(f"LLM generation failed: {last_error}")
