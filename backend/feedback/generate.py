"""Stage 6 - feedback prose (PIPELINE.md).

Turns the numeric per-move metrics into short coaching notes and an overall
summary. This is the ONLY place the Anthropic API is used in the product
(CLAUDE.md - Feedback Generation). Keep it isolated here.

Hard rules from the docs:
- Input is the structured metrics ONLY. NEVER raw video, NEVER raw landmark
  arrays. Vision produced numbers; language only interprets them.
- Output prose is grounded strictly in the numbers passed in. The prompt
  instructs the model to describe only what the metrics show.
- Low-confidence moves are described as low-confidence, never given a
  confident correction.
"""

import json
import logging
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Structured outputs guarantee the response parses; the schema mirrors what the
# analyze endpoint persists to the `analyses` and `moves` tables (CLAUDE.md).
MODEL = "claude-opus-4-8"
MAX_TOKENS = 4000

SYSTEM_PROMPT = """\
You are a climbing technique coach writing feedback from computed metrics.

You receive per-move metrics from a computer-vision analysis of one climb:
- move_type: "static" (a controlled reach) or "dynamic" (a lunge/dyno).
- cog_distance (static moves only): the climber's center-of-mass distance to
  the target hold at the moment of the reach, in normalized frame units
  (0..~1, where ~0.05 is very close and ~0.4 is very far). Smaller means the
  center of mass was well-positioned under the reach - better technique.
- landing_control (dynamic moves only): mean center-of-mass speed just after
  the target hold was caught, in normalized units per second. Smaller means a
  more settled, controlled catch.
- confidence / low_confidence: pose-tracking confidence for the move's frames.

Rules you must follow:
1. Ground every statement strictly in the numbers provided. Never invent
   detail the metrics do not support (grip, body angle, footwork, effort).
2. Never criticize a dynamic move for its center of mass being far from the
   target mid-move - a lunge requires that. Judge dynamic moves only on
   landing control. Never speculate about whether the dyno was necessary.
3. For any move marked low_confidence, say the tracking was not reliable
   enough to assess it confidently, and do not give a confident correction.
4. Keep each note to one or two sentences, plain language, actionable where
   the numbers support it. The overall summary is two to four sentences and
   presents center-of-mass positioning as one lens on technique, not a
   definitive judgment of the climb.\
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "move_index": {"type": "integer"},
                    "note": {"type": "string"},
                },
                "required": ["move_index", "note"],
                "additionalProperties": False,
            },
        },
        "overall_summary": {"type": "string"},
    },
    "required": ["notes", "overall_summary"],
    "additionalProperties": False,
}


class MoveMetrics(BaseModel):
    """Per-move metrics as produced by the client pipeline (PIPELINE.md Stage 4).

    Exactly the shape persisted to the `moves` table. Will move to
    models/schemas.py when the analyze endpoint is built in Phase 2.
    """

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


def _route_aggregates(moves: list[MoveMetrics]) -> dict[str, object]:
    """Route-level aggregates passed alongside the per-move metrics."""
    static_distances = [
        m.cog_distance for m in moves
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


def generate_feedback(
    moves: list[MoveMetrics],
    client: anthropic.Anthropic | None = None,
) -> FeedbackResult:
    """Generate per-move notes and an overall summary from numeric metrics.

    Accepts an injected client for testing; by default builds one from the
    ANTHROPIC_API_KEY environment variable (loaded via core.config / .env).
    Raises ValueError on empty input and lets anthropic.APIError surface to
    the caller (the analyze endpoint maps it to a 500 without leaking details).
    """
    if not moves:
        raise ValueError("cannot generate feedback for zero moves")

    if client is None:
        from core.config import get_settings

        client = anthropic.Anthropic(api_key=get_settings().anthropic_api_key)

    payload = {
        "moves": [m.model_dump() for m in moves],
        "route_aggregates": _route_aggregates(moves),
    }

    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": (
                    "Write coaching feedback for this climb. Metrics:\n"
                    + json.dumps(payload, sort_keys=True)
                ),
            }
        ],
    )

    if response.stop_reason == "refusal":
        # Metrics-only input should never trip safety; treat as an internal error.
        logger.error("feedback generation refused: %s", response.stop_details)
        raise RuntimeError("feedback generation was refused by the model")

    text = next(block.text for block in response.content if block.type == "text")
    result = FeedbackResult.model_validate_json(text)

    # Belt and braces: every move must get a note, in move order.
    note_indices = {n.move_index for n in result.notes}
    missing = [m.move_index for m in moves if m.move_index not in note_indices]
    if missing:
        logger.error("feedback missing notes for moves %s", missing)
        raise RuntimeError(f"feedback generation returned no note for moves {missing}")
    result.notes.sort(key=lambda n: n.move_index)
    return result
