"""Shared types for the feedback layer and the provider interface.

The feedback layer turns numeric per-move metrics into coaching prose. It is a
SETTLED separation (PIPELINE.md, CLAUDE.md): the language/generation layer sees
ONLY the computed numbers - never raw video, never landmark arrays. Providers
differ only in HOW the prose is produced (deterministic templates, a local LLM,
or a hosted LLM); the input contract and grounding rules are identical.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field


class MoveMetrics(BaseModel):
    """Per-move metrics as produced by scoring (PIPELINE.md Stage 4). Exactly
    the numbers a provider is allowed to see."""

    move_index: int
    target_hold_sequence_index: int
    move_type: Literal["static", "dynamic"]
    cog_distance: float | None = None
    landing_control: float | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    low_confidence: bool


class MoveNote(BaseModel):
    move_index: int
    note: str


class FeedbackResult(BaseModel):
    notes: list[MoveNote]
    overall_summary: str


class FeedbackProvider(Protocol):
    """Turns per-move metrics into a per-move note + overall summary. Must
    return a note for every move, grounded strictly in the metrics."""

    def generate(self, moves: list[MoveMetrics]) -> FeedbackResult: ...


def route_aggregates(moves: list[MoveMetrics]) -> dict[str, object]:
    """Route-level aggregates shared by all providers (and handy for prompts)."""
    static_distances = [
        m.cog_distance
        for m in moves
        if m.move_type == "static" and m.cog_distance is not None and not m.low_confidence
    ]
    return {
        "total_moves": len(moves),
        "static_moves": sum(1 for m in moves if m.move_type == "static"),
        "dynamic_moves": sum(1 for m in moves if m.move_type == "dynamic"),
        "low_confidence_moves": sum(1 for m in moves if m.low_confidence),
        "mean_static_cog_distance": (
            sum(static_distances) / len(static_distances) if static_distances else None
        ),
    }
