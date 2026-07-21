"""Feedback layer entry point: pick a provider and turn metrics into prose.

Providers (selected by FEEDBACK_PROVIDER, see core/config.py):
- "template"  - deterministic grounded prose, no LLM (default; no key/deps).
- "ollama"    - a local LLM via Ollama (free, private, no key).
- "anthropic" - the hosted Anthropic API (optional; needs ANTHROPIC_API_KEY).

The provider only ever sees numeric metrics (MoveMetrics) - never raw video or
landmark arrays (CLAUDE.md, PIPELINE.md Stage 6). Re-exports MoveMetrics /
FeedbackResult so callers keep importing them from here.
"""

from __future__ import annotations

import logging

from core.config import Settings
from feedback.base import FeedbackProvider, FeedbackResult, MoveMetrics, MoveNote
from feedback.template import TemplateProvider

logger = logging.getLogger("optimalclimbing")

__all__ = ["MoveMetrics", "MoveNote", "FeedbackResult", "generate_feedback", "resolve_provider"]


def resolve_provider(settings: Settings) -> FeedbackProvider:
    """Build the configured feedback provider. LLM providers are imported lazily
    so the default (template) path needs no LLM client at all."""
    name = settings.feedback_provider
    if name == "template":
        return TemplateProvider()
    if name == "ollama":
        from feedback.ollama_provider import OllamaProvider

        return OllamaProvider(settings.ollama_url, settings.ollama_model)
    if name == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "FEEDBACK_PROVIDER=anthropic requires ANTHROPIC_API_KEY in the environment"
            )
        from feedback.anthropic_provider import AnthropicProvider

        return AnthropicProvider(settings.anthropic_api_key)
    raise RuntimeError(
        f"Unknown FEEDBACK_PROVIDER '{name}' (expected template | ollama | anthropic)"
    )


def generate_feedback(moves: list[MoveMetrics], provider: FeedbackProvider) -> FeedbackResult:
    """Generate per-move notes + an overall summary using `provider`.

    Enforces the invariant every provider must satisfy: exactly one note per
    move, in move order. Raises ValueError on empty input; lets provider errors
    surface to the caller (the analyze endpoint maps them to a 500).
    """
    if not moves:
        raise ValueError("cannot generate feedback for zero moves")

    result = provider.generate(moves)

    note_indices = {n.move_index for n in result.notes}
    missing = [m.move_index for m in moves if m.move_index not in note_indices]
    if missing:
        logger.error("feedback missing notes for moves %s", missing)
        raise RuntimeError(f"feedback generation returned no note for moves {missing}")
    result.notes.sort(key=lambda n: n.move_index)
    return result
