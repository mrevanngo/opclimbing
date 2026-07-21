"""Hosted-LLM feedback provider via the Anthropic API (optional).

No longer the default (FEEDBACK_PROVIDER=template is). Enable with
FEEDBACK_PROVIDER=anthropic and a valid ANTHROPIC_API_KEY. Uses structured
outputs so the response is guaranteed-parseable JSON.
"""

from __future__ import annotations

import logging

import anthropic

from feedback.base import FeedbackResult, MoveMetrics
from feedback.llm_prompt import OUTPUT_SCHEMA, SYSTEM_PROMPT, build_user_message

logger = logging.getLogger("optimalclimbing")

_MODEL = "claude-opus-4-8"
_MAX_TOKENS = 4000


class AnthropicProvider:
    def __init__(self, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def generate(self, moves: list[MoveMetrics]) -> FeedbackResult:
        response = self._client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
            messages=[{"role": "user", "content": build_user_message(moves)}],
        )
        if response.stop_reason == "refusal":
            logger.error("feedback generation refused: %s", response.stop_details)
            raise RuntimeError("feedback generation was refused by the model")
        text = next(block.text for block in response.content if block.type == "text")
        return FeedbackResult.model_validate_json(text)
