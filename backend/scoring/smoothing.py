"""Server-side port of Stage 3 - smoothing. Mirrors
frontend/src/pipeline/smoothing.ts: a one-euro filter over the CoM position
series, then central-difference velocity and acceleration. See PIPELINE.md - Stage 3.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from scoring.cog import CoGPoint


@dataclass(frozen=True)
class OneEuroParams:
    min_cutoff: float
    beta: float
    d_cutoff: float


DEFAULT_ONE_EURO = OneEuroParams(min_cutoff=1.0, beta=0.5, d_cutoff=1.0)


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float


@dataclass(frozen=True)
class SmoothedTrajectory:
    frame_rate: float
    points: list[CoGPoint]
    velocity: list[Point2D]
    acceleration: list[Point2D]


def _smoothing_factor(cutoff: float, dt: float) -> float:
    r = 2 * math.pi * cutoff * dt
    return r / (r + 1)


class _OneEuroFilter:
    """One-euro filter over a scalar series sampled at 1/dt Hz."""

    def __init__(self, params: OneEuroParams, dt: float) -> None:
        self._params = params
        self._dt = dt
        self._prev_value: float | None = None
        self._prev_derivative = 0.0

    def next(self, value: float) -> float:
        if self._prev_value is None:
            self._prev_value = value
            return value
        raw_derivative = (value - self._prev_value) / self._dt
        a_d = _smoothing_factor(self._params.d_cutoff, self._dt)
        derivative = a_d * raw_derivative + (1 - a_d) * self._prev_derivative
        cutoff = self._params.min_cutoff + self._params.beta * abs(derivative)
        a = _smoothing_factor(cutoff, self._dt)
        smoothed = a * value + (1 - a) * self._prev_value
        self._prev_value = smoothed
        self._prev_derivative = derivative
        return smoothed


def _differentiate(series: list[Point2D], dt: float) -> list[Point2D]:
    """Central-difference derivative (forward/backward at the ends)."""
    n = len(series)
    if n == 0:
        return []
    if n == 1:
        return [Point2D(0.0, 0.0)]
    out: list[Point2D] = [Point2D(0.0, 0.0)] * n
    out[0] = Point2D((series[1].x - series[0].x) / dt, (series[1].y - series[0].y) / dt)
    for i in range(1, n - 1):
        out[i] = Point2D(
            (series[i + 1].x - series[i - 1].x) / (2 * dt),
            (series[i + 1].y - series[i - 1].y) / (2 * dt),
        )
    out[n - 1] = Point2D(
        (series[n - 1].x - series[n - 2].x) / dt,
        (series[n - 1].y - series[n - 2].y) / dt,
    )
    return out


def magnitude(v: Point2D) -> float:
    return math.hypot(v.x, v.y)


def smooth_trajectory(
    trajectory: list[CoGPoint],
    frame_rate: float,
    params: OneEuroParams = DEFAULT_ONE_EURO,
) -> SmoothedTrajectory:
    if frame_rate <= 0:
        raise ValueError(f"frame_rate must be positive, got {frame_rate}")
    dt = 1 / frame_rate

    filter_x = _OneEuroFilter(params, dt)
    filter_y = _OneEuroFilter(params, dt)
    points = [
        CoGPoint(x=filter_x.next(p.x), y=filter_y.next(p.y), confidence=p.confidence)
        for p in trajectory
    ]
    position = [Point2D(p.x, p.y) for p in points]
    velocity = _differentiate(position, dt)
    acceleration = _differentiate(velocity, dt)
    return SmoothedTrajectory(
        frame_rate=frame_rate, points=points, velocity=velocity, acceleration=acceleration
    )
