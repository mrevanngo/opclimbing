// Stage 3 - smoothing (PIPELINE.md). Landmarks jitter frame to frame and the CoM
// inherits it; velocity and acceleration amplify that noise badly. Smooth the CoM
// position series first, then differentiate the smoothed series.
//
// Filter choice: one-euro filter (PIPELINE.md's suggested default) - low latency,
// two intuitive knobs, no over-engineering.

import type { CoGPoint, Point2D, SmoothedTrajectory } from './types';

export interface OneEuroParams {
  /** Cutoff (Hz) at low speeds. Lower = more smoothing of slow jitter. */
  minCutoff: number;
  /** How much the cutoff opens up with speed. Higher = less lag on fast moves. */
  beta: number;
  /** Cutoff (Hz) for the internal derivative estimate. */
  dCutoff: number;
}

/**
 * Defaults tuned for normalized-coordinate CoM at phone frame rates. The bar
 * from PIPELINE.md: a real dynamic move must be clearly separable from jitter
 * in the acceleration signal. Re-tune against the fixture clip if it is not.
 */
export const DEFAULT_ONE_EURO: OneEuroParams = {
  minCutoff: 1.0,
  beta: 0.5,
  dCutoff: 1.0,
};

function smoothingFactor(cutoff: number, dt: number): number {
  const r = 2 * Math.PI * cutoff * dt;
  return r / (r + 1);
}

/** Standard one-euro filter over a scalar series sampled at 1/dt Hz. */
class OneEuroFilter {
  private prevValue: number | null = null;
  private prevDerivative = 0;
  private readonly params: OneEuroParams;
  private readonly dt: number;

  constructor(params: OneEuroParams, dt: number) {
    this.params = params;
    this.dt = dt;
  }

  next(value: number): number {
    if (this.prevValue === null) {
      this.prevValue = value;
      return value;
    }
    // Estimate the signal's rate of change, itself low-pass filtered.
    const rawDerivative = (value - this.prevValue) / this.dt;
    const aD = smoothingFactor(this.params.dCutoff, this.dt);
    const derivative = aD * rawDerivative + (1 - aD) * this.prevDerivative;
    // Open the cutoff with speed so fast real motion lags less.
    const cutoff = this.params.minCutoff + this.params.beta * Math.abs(derivative);
    const a = smoothingFactor(cutoff, this.dt);
    const smoothed = a * value + (1 - a) * this.prevValue;
    this.prevValue = smoothed;
    this.prevDerivative = derivative;
    return smoothed;
  }
}

/**
 * Smooth a CoM trajectory and derive velocity and acceleration from the
 * smoothed series. Confidence is carried through unchanged - smoothing does not
 * make a low-confidence frame trustworthy.
 */
export function smoothTrajectory(
  trajectory: CoGPoint[],
  frameRate: number,
  params: OneEuroParams = DEFAULT_ONE_EURO,
): SmoothedTrajectory {
  if (frameRate <= 0) {
    throw new Error(`frameRate must be positive, got ${frameRate}`);
  }
  const dt = 1 / frameRate;

  const filterX = new OneEuroFilter(params, dt);
  const filterY = new OneEuroFilter(params, dt);
  const points: CoGPoint[] = trajectory.map((p) => ({
    x: filterX.next(p.x),
    y: filterY.next(p.y),
    confidence: p.confidence,
  }));

  const velocity = differentiate(points, dt);
  const acceleration = differentiate(velocity, dt);

  return { frameRate, points, velocity, acceleration };
}

/**
 * Central-difference derivative of a 2D series (forward/backward at the ends).
 * Central differences halve the noise of one-sided differences and have no
 * phase lag, which matters because Stage 4 thresholds on these values.
 */
function differentiate(series: Point2D[], dt: number): Point2D[] {
  const n = series.length;
  if (n === 0) return [];
  if (n === 1) return [{ x: 0, y: 0 }];
  const out: Point2D[] = new Array(n);
  out[0] = {
    x: (series[1].x - series[0].x) / dt,
    y: (series[1].y - series[0].y) / dt,
  };
  for (let i = 1; i < n - 1; i++) {
    out[i] = {
      x: (series[i + 1].x - series[i - 1].x) / (2 * dt),
      y: (series[i + 1].y - series[i - 1].y) / (2 * dt),
    };
  }
  out[n - 1] = {
    x: (series[n - 1].x - series[n - 2].x) / dt,
    y: (series[n - 1].y - series[n - 2].y) / dt,
  };
  return out;
}

/** Scalar magnitude helper for velocity/acceleration vectors. */
export function magnitude(v: Point2D): number {
  return Math.hypot(v.x, v.y);
}
