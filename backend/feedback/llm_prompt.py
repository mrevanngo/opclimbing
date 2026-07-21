"""Shared prompt + output schema for the LLM-backed feedback providers
(Ollama, Anthropic). The grounding rules are identical across providers - only
the transport differs. The model receives ONLY numeric metrics.
"""

from __future__ import annotations

import json

from feedback.base import MoveMetrics, route_aggregates

SYSTEM_PROMPT = """\
You are a climbing technique coach writing feedback from computed metrics.

You receive per-move metrics from a computer-vision analysis of one climb:
- move_type: "static" (a controlled reach) or "dynamic" (a lunge/dyno).
- cog_distance (static moves only): the climber's center-of-mass distance to the
  target hold at the moment of the reach, in normalized frame units (~0.05 is
  very close, ~0.4 is very far). Smaller = better positioned under the reach.
- landing_control (dynamic moves only): mean center-of-mass speed just after the
  hold is caught, normalized units/second. Smaller = a more settled, controlled catch.
- confidence / low_confidence: pose-tracking confidence for the move.

Rules you MUST follow:
1. Ground every statement strictly in the numbers provided. Never invent detail
   the metrics do not support (grip, exact body angle, footwork, effort).
2. Never criticize a dynamic move for its center of mass being far from the
   target mid-move - a lunge requires that. Judge dynamic moves only on landing
   control. Never speculate about whether the dyno was necessary.
3. For any move marked low_confidence, say the tracking was not reliable enough
   to assess it and do not give a confident correction.
4. Each note is one or two plain-language sentences, actionable where the numbers
   support it. The overall summary is two to four sentences and frames
   center-of-mass proximity as one lens on technique, not a definitive judgment."""

# JSON Schema (used directly by Anthropic structured outputs; described in the
# prompt for Ollama's JSON mode).
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


def build_user_message(moves: list[MoveMetrics]) -> str:
    payload = {
        "moves": [m.model_dump() for m in moves],
        "route_aggregates": route_aggregates(moves),
    }
    return (
        "Write coaching feedback for this climb. Return ONLY a JSON object with "
        '"notes" (one {"move_index", "note"} per move) and "overall_summary". '
        "Metrics:\n" + json.dumps(payload, sort_keys=True)
    )
