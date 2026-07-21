"""Local-LLM feedback provider via Ollama (http://localhost:11434).

Free, private, no API key - the model runs on the user's machine. Enable with
FEEDBACK_PROVIDER=ollama (see core/config.py). Recommended model: qwen2.5:7b
(strong at faithful, structured output at 8 GB VRAM); llama3.1:8b is a safe
alternative. Install: https://ollama.com, then `ollama pull qwen2.5:7b`.
"""

from __future__ import annotations

import logging

import httpx

from feedback.base import FeedbackResult, MoveMetrics
from feedback.llm_prompt import SYSTEM_PROMPT, build_user_message

logger = logging.getLogger("optimalclimbing")


class OllamaProvider:
    def __init__(self, url: str, model: str) -> None:
        self._url = url.rstrip("/")
        self._model = model

    def generate(self, moves: list[MoveMetrics]) -> FeedbackResult:
        body = {
            "model": self._model,
            "stream": False,
            "format": "json",  # force valid JSON output
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(moves)},
            ],
        }
        try:
            resp = httpx.post(f"{self._url}/api/chat", json=body, timeout=180.0)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("ollama request failed: %s", exc)
            raise RuntimeError(
                f"Local LLM (Ollama) unreachable at {self._url}. Is `ollama serve` "
                f"running and is the model '{self._model}' pulled?"
            ) from exc

        content = resp.json().get("message", {}).get("content", "")
        try:
            return FeedbackResult.model_validate_json(content)
        except ValueError as exc:
            logger.error("ollama returned unparseable feedback: %s", content[:500])
            raise RuntimeError("Local LLM returned malformed feedback JSON") from exc
