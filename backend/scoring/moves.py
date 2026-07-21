"""Server-side port of Stage 4 - move segmentation, static/dynamic
classification, per-move metrics. Mirrors frontend/src/pipeline/moves.ts.
See PIPELINE.md - Stage 4.

Settled Decision: static vs dynamic by a velocity/acceleration threshold on the
smoothed CoM trajectory, NOT a trained classifier in V1. Static moves are scored
on CoM-to-target distance at the reach; dynamic moves on landing control only
(never mid-move distance - a lunge requires the CoM to be far). No "was the dyno
necessary" judgment (deferred).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from scoring.cog import LEFT_WRIST, RIGHT_WRIST, Frame
from scoring.smoothing import SmoothedTrajectory, magnitude

MoveType = Literal["static", "dynamic"]


@dataclass(frozen=True)
class MoveParams:
    arrival_radius: float = 0.05
    dynamic_accel_threshold: float = 3.0
    landing_window_seconds: float = 0.3
    confidence_threshold: float = 0.5


MOVE_PARAMS = MoveParams()


@dataclass(frozen=True)
class Hold:
    sequence_index: int
    frame_x: float
    frame_y: float
    id: str | None = None  # server-side hold id, when known


@dataclass(frozen=True)
class Move:
    move_index: int
    target_hold_sequence_index: int
    target_hold_id: str | None
    move_type: MoveType
    cog_distance: float | None
    landing_control: float | None
    confidence: float
    low_confidence: bool
    start_frame: int
    end_frame: int


def _distance(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def _wrist_distance_to_hold(frame: Frame, hold: Hold) -> float:
    lw = frame[LEFT_WRIST]
    rw = frame[RIGHT_WRIST]
    return min(
        _distance(lw.x, lw.y, hold.frame_x, hold.frame_y),
        _distance(rw.x, rw.y, hold.frame_x, hold.frame_y),
    )


def _find_arrival_frame(frames: list[Frame], hold: Hold, from_frame: int) -> int:
    """First frame from `from_frame` where a wrist is within the arrival radius;
    else the frame where a wrist gets closest (so segmentation still produces a
    window even if the hold was never cleanly reached)."""
    best_frame = from_frame
    best_dist = math.inf
    for i in range(from_frame, len(frames)):
        d = _wrist_distance_to_hold(frames[i], hold)
        if d < MOVE_PARAMS.arrival_radius:
            return i
        if d < best_dist:
            best_dist = d
            best_frame = i
    return best_frame


def classify_moves(
    frames: list[Frame], trajectory: SmoothedTrajectory, holds: list[Hold]
) -> list[Move]:
    if len(frames) != len(trajectory.points):
        raise ValueError(
            f"frames ({len(frames)}) and trajectory ({len(trajectory.points)}) lengths differ"
        )
    if not holds:
        raise ValueError("cannot segment moves with zero annotated holds")

    ordered = sorted(holds, key=lambda h: h.sequence_index)
    moves: list[Move] = []
    window_start = _find_arrival_frame(frames, ordered[0], 0)

    for h in range(1, len(ordered)):
        hold = ordered[h]
        search_from = min(window_start + 1, len(frames) - 1)
        arrival = _find_arrival_frame(frames, hold, search_from)
        start_frame = window_start
        end_frame = max(arrival, start_frame)
        moves.append(_score_move(len(moves), hold, start_frame, end_frame, trajectory))
        window_start = end_frame

    return moves


def _score_move(
    move_index: int, hold: Hold, start_frame: int, end_frame: int, trajectory: SmoothedTrajectory
) -> Move:
    points = trajectory.points
    acceleration = trajectory.acceleration
    frame_rate = trajectory.frame_rate

    peak_accel = 0.0
    confidence_sum = 0.0
    for i in range(start_frame, end_frame + 1):
        peak_accel = max(peak_accel, magnitude(acceleration[i]))
        confidence_sum += points[i].confidence
    confidence = confidence_sum / (end_frame - start_frame + 1)
    move_type: MoveType = (
        "dynamic" if peak_accel > MOVE_PARAMS.dynamic_accel_threshold else "static"
    )

    cog_distance: float | None = None
    landing_control: float | None = None
    if move_type == "static":
        cog = points[end_frame]
        cog_distance = _distance(cog.x, cog.y, hold.frame_x, hold.frame_y)
    else:
        landing_frames = max(1, round(MOVE_PARAMS.landing_window_seconds * frame_rate))
        landing_end = min(end_frame + landing_frames, len(points) - 1)
        speed_sum = 0.0
        count = 0
        for i in range(end_frame, landing_end + 1):
            speed_sum += magnitude(trajectory.velocity[i])
            count += 1
        landing_control = speed_sum / count

    return Move(
        move_index=move_index,
        target_hold_sequence_index=hold.sequence_index,
        target_hold_id=hold.id,
        move_type=move_type,
        cog_distance=cog_distance,
        landing_control=landing_control,
        confidence=confidence,
        low_confidence=confidence < MOVE_PARAMS.confidence_threshold,
        start_frame=start_frame,
        end_frame=end_frame,
    )
