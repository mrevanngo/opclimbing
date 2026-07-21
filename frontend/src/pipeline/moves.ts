// Stage 4 - move segmentation, static/dynamic classification, per-move metrics
// (PIPELINE.md). Settled Decision: static vs dynamic by a velocity/acceleration
// threshold on the smoothed CoM trajectory, NOT a trained classifier in V1.
//
// Segmentation ties each move window to the interval ending when a hand reaches
// the next annotated hold (tap order = intended sequence). Deliberately simple
// and explainable.

import { LANDMARK } from './cog';
import { magnitude } from './smoothing';
import type { FrameLandmarks, Hold, Move, SmoothedTrajectory } from './types';

/**
 * Tunable thresholds, named so they can be re-tuned against the fixture clip.
 * All distances are in normalized frame units; time-derived values use real
 * seconds via the frame rate.
 */
export const MOVE_PARAMS = {
  /** A wrist within this distance of a hold counts as arrived at it. */
  arrivalRadius: 0.05,
  /**
   * Peak CoM acceleration (normalized units/s^2) above which a move is dynamic.
   * A controlled static reach barely accelerates the CoM; a lunge/dyno produces
   * a sharp spike an order of magnitude larger. Re-tune on real footage.
   */
  dynamicAccelThreshold: 3.0,
  /** Seconds after the catch over which landing control is measured. */
  landingWindowSeconds: 0.3,
  /** Mean pose confidence below which a move is flagged low-confidence. */
  confidenceThreshold: 0.5,
} as const;

export type MoveParams = typeof MOVE_PARAMS;

function distance(ax: number, ay: number, bx: number, by: number): number {
  return Math.hypot(ax - bx, ay - by);
}

/** Nearest-wrist distance to a hold for one frame. */
function wristDistanceToHold(frame: FrameLandmarks, hold: Hold): number {
  const lw = frame[LANDMARK.LEFT_WRIST];
  const rw = frame[LANDMARK.RIGHT_WRIST];
  return Math.min(
    distance(lw.x, lw.y, hold.frameX, hold.frameY),
    distance(rw.x, rw.y, hold.frameX, hold.frameY),
  );
}

/**
 * Find the frame at which a hand arrives at the hold, searching from
 * `fromFrame`: the first frame where a wrist is within the arrival radius. If
 * no frame qualifies (hold missed, occlusion), fall back to the frame where a
 * wrist gets closest, so segmentation still produces a window.
 */
function findArrivalFrame(frames: FrameLandmarks[], hold: Hold, fromFrame: number): number {
  let bestFrame = fromFrame;
  let bestDist = Number.POSITIVE_INFINITY;
  for (let i = fromFrame; i < frames.length; i++) {
    const d = wristDistanceToHold(frames[i], hold);
    if (d < MOVE_PARAMS.arrivalRadius) return i;
    if (d < bestDist) {
      bestDist = d;
      bestFrame = i;
    }
  }
  return bestFrame;
}

/**
 * Segment the climb into moves and score each one.
 *
 * - Holds must be the user's annotated set; tap order = intended sequence.
 * - The first hold in sequence is treated as the starting hold; every
 *   subsequent hold defines one move (the reach toward it).
 * - Static moves are scored on CoM-to-target distance at the reach.
 * - Dynamic moves are scored on landing control ONLY - mid-move CoM distance is
 *   never scored, because a lunge requires the CoM to be far from the target.
 *   No "was this dyno necessary" judgment (deferred).
 */
export function classifyMoves(
  frames: FrameLandmarks[],
  trajectory: SmoothedTrajectory,
  holds: Hold[],
): Move[] {
  if (frames.length !== trajectory.points.length) {
    throw new Error(
      `frames (${frames.length}) and trajectory (${trajectory.points.length}) lengths differ`,
    );
  }
  if (holds.length === 0) {
    throw new Error('cannot segment moves with zero annotated holds');
  }

  const ordered = [...holds].sort((a, b) => a.sequenceIndex - b.sequenceIndex);
  const moves: Move[] = [];
  let windowStart = findArrivalFrame(frames, ordered[0], 0);

  for (let h = 1; h < ordered.length; h++) {
    const hold = ordered[h];
    const searchFrom = Math.min(windowStart + 1, frames.length - 1);
    const arrival = findArrivalFrame(frames, hold, searchFrom);
    const startFrame = windowStart;
    const endFrame = Math.max(arrival, startFrame);

    moves.push(scoreMove(moves.length, hold, startFrame, endFrame, trajectory));
    windowStart = endFrame;
  }

  return moves;
}

function scoreMove(
  moveIndex: number,
  hold: Hold,
  startFrame: number,
  endFrame: number,
  trajectory: SmoothedTrajectory,
): Move {
  const { points, acceleration, frameRate } = trajectory;

  let peakAccel = 0;
  let confidenceSum = 0;
  for (let i = startFrame; i <= endFrame; i++) {
    peakAccel = Math.max(peakAccel, magnitude(acceleration[i]));
    confidenceSum += points[i].confidence;
  }
  const confidence = confidenceSum / (endFrame - startFrame + 1);
  const moveType = peakAccel > MOVE_PARAMS.dynamicAccelThreshold ? 'dynamic' : 'static';

  let cogDistance: number | null = null;
  let landingControl: number | null = null;
  if (moveType === 'static') {
    // Core metric: how close the CoM was to the target at the moment of the reach.
    const cog = points[endFrame];
    cogDistance = distance(cog.x, cog.y, hold.frameX, hold.frameY);
  } else {
    // Landing control: mean CoM speed over the window just after the catch.
    // A settled CoM means the dyno was caught in control.
    const landingFrames = Math.max(1, Math.round(MOVE_PARAMS.landingWindowSeconds * frameRate));
    const landingEnd = Math.min(endFrame + landingFrames, points.length - 1);
    let speedSum = 0;
    let count = 0;
    for (let i = endFrame; i <= landingEnd; i++) {
      speedSum += magnitude(trajectory.velocity[i]);
      count++;
    }
    landingControl = speedSum / count;
  }

  return {
    moveIndex,
    targetHoldId: hold.id,
    targetHoldSequenceIndex: hold.sequenceIndex,
    moveType,
    cogDistance,
    landingControl,
    confidence,
    lowConfidence: confidence < MOVE_PARAMS.confidenceThreshold,
    startFrame,
    endFrame,
  };
}
