"""Deterministic template feedback provider (the default).

Turns per-move metrics into grounded coaching prose with no LLM and no external
dependency. Because every sentence is derived directly from the numbers, it
cannot invent detail the metrics do not support - which is exactly what the
product requires (PRD: grounded strictly in the numbers; low-confidence moves
described as such, not given a confident correction).

The distance/landing bands are heuristics (like MOVE_PARAMS in the pipeline) and
are tunable as more real footage is scored.
"""

from __future__ import annotations

from feedback.base import FeedbackResult, MoveMetrics, MoveNote, route_aggregates

# Normalized-frame-unit bands for the static CoM-to-target distance at the reach.
_CLOSE = 0.12
_FAR = 0.22
# Normalized units/second bands for dynamic landing control (CoM speed at catch).
_LANDING_CONTROLLED = 0.15
_LANDING_LOOSE = 0.35

_LOW_CONF_NOTE = (
    "Pose tracking was unreliable for this move, so this is not a confident "
    "assessment - re-film with the climber more clearly in frame for a better read."
)


def _static_note(distance: float) -> str:
    if distance < _CLOSE:
        phrase = "your center of mass was well under the reach"
        advice = "nicely controlled - keep setting your hips like this."
    elif distance < _FAR:
        phrase = "your center of mass was a bit far from the hold"
        advice = "shifting your hips closer before you reach would make it more controlled."
    else:
        phrase = "your center of mass was well away from the hold, so the reach was a stretch"
        advice = "set your feet to bring your center of mass under the hold before reaching."
    return f"{phrase} ({distance:.2f} from the target at the reach) - {advice}"


def _dynamic_note(landing_control: float | None) -> str:
    if landing_control is None:
        return "Dynamic move - scored on the control of the catch."
    if landing_control < _LANDING_CONTROLLED:
        phrase = "a controlled, settled catch"
        advice = "well done - the landing was in balance."
    elif landing_control < _LANDING_LOOSE:
        phrase = "some residual motion on the catch"
        advice = "engaging your core earlier on the catch would steady it."
    else:
        phrase = "a loose catch with a lot of motion"
        advice = "aim to absorb the swing and lock off sooner."
    return (
        f"Dynamic move: {phrase} ({landing_control:.2f} of residual center-of-mass "
        f"motion as you caught the hold) - {advice}"
    )


def _overall(moves: list[MoveMetrics]) -> str:
    agg = route_aggregates(moves)
    total = agg["total_moves"]
    static = agg["static_moves"]
    dynamic = agg["dynamic_moves"]
    mean = agg["mean_static_cog_distance"]
    low = agg["low_confidence_moves"]

    parts = [f"Analyzed {total} move{'s' if total != 1 else ''} ({static} static, {dynamic} dynamic)."]
    if isinstance(mean, float):
        if mean < _CLOSE:
            band = "consistently well-positioned under your reaches"
        elif mean < _FAR:
            band = "a little far on average, with room to get your hips closer under the reach"
        else:
            band = "often far from the target, so several reaches were stretches"
        parts.append(f"Across your static reaches your center of mass averaged {mean:.2f} from the target - {band}.")
    if dynamic:
        parts.append("Dynamic moves are judged on how settled the catch was, not on reach distance.")
    if low:
        parts.append(f"{low} move{'s were' if low != 1 else ' was'} low-confidence and not assessed firmly.")
    parts.append("Center-of-mass proximity is one lens on technique, not a full judgment of the climb.")
    return " ".join(parts)


class TemplateProvider:
    """Deterministic, dependency-free feedback. The default provider."""

    def generate(self, moves: list[MoveMetrics]) -> FeedbackResult:
        notes: list[MoveNote] = []
        for m in moves:
            if m.low_confidence:
                text = _LOW_CONF_NOTE
            elif m.move_type == "static" and m.cog_distance is not None:
                text = _static_note(m.cog_distance)
            elif m.move_type == "dynamic":
                text = _dynamic_note(m.landing_control)
            else:
                text = "Move recorded, but its metric was unavailable."
            notes.append(MoveNote(move_index=m.move_index, note=text))
        return FeedbackResult(notes=notes, overall_summary=_overall(moves))
