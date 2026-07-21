// Shared types for the analysis pipeline. Each stage's output is the next stage's
// input; the stage contracts are defined in PIPELINE.md and must stay in sync with it.

/** One MediaPipe pose landmark in normalized frame coordinates. */
export interface Landmark {
  /** Normalized horizontal position, 0..1 (left to right in the frame). */
  x: number;
  /** Normalized vertical position, 0..1 (top to bottom in the frame). */
  y: number;
  /**
   * Rough depth relative to the hips. UNRELIABLE - never build scored logic on it
   * (Settled Decision: depth is not scored in V1).
   */
  z: number;
  /** Per-landmark visibility/presence score, 0..1. */
  visibility: number;
}

/** All 33 MediaPipe pose landmarks for a single video frame. */
export type FrameLandmarks = Landmark[];

/** Stage 1 output: per-frame landmarks plus the sampling rate used to extract them. */
export interface PoseResult {
  /** Frames per second the video was sampled at. Later stages need real time. */
  frameRate: number;
  /** One entry per analyzed frame, each holding 33 landmarks. */
  frames: FrameLandmarks[];
}

/** A 2D point in normalized frame coordinates. */
export interface Point2D {
  x: number;
  y: number;
}

/** Stage 2 output: the whole-body center of mass for one frame. */
export interface CoGPoint extends Point2D {
  /**
   * Confidence for this frame's CoM: mean visibility of the landmarks the
   * segmental model uses. Low values propagate downstream - a move built from
   * low-visibility frames is flagged low-confidence, never scored confidently.
   */
  confidence: number;
}

/** Stage 3 output: smoothed trajectory with time derivatives. */
export interface SmoothedTrajectory {
  frameRate: number;
  /** Smoothed CoM position per frame (confidence carried through unchanged). */
  points: CoGPoint[];
  /** CoM velocity per frame in normalized units per second. */
  velocity: Point2D[];
  /** CoM acceleration per frame in normalized units per second squared. */
  acceleration: Point2D[];
}

/** A user-annotated hold. Tap order = intended sequence (see CLAUDE.md schema). */
export interface Hold {
  /** Server-side id when the hold set has been persisted; absent before then. */
  id?: string;
  /** 0-based tap order = intended usage sequence. */
  sequenceIndex: number;
  /** Normalized frame coordinates of the hold. */
  frameX: number;
  frameY: number;
}

export type MoveType = 'static' | 'dynamic';

/**
 * Stage 4 output, one per move. Mirrors the `moves` table and the metrics
 * passed to the feedback layer (see CLAUDE.md).
 */
export interface Move {
  /** 0-based, ordered. */
  moveIndex: number;
  /** The hold this move reaches for (by sequence index; id once persisted). */
  targetHoldId?: string;
  targetHoldSequenceIndex: number;
  moveType: MoveType;
  /**
   * Static moves only: normalized CoM-to-target-hold distance at the moment of
   * the reach. Smaller = better positioned. Null for dynamic moves - a lunge
   * REQUIRES the CoM to be far, and penalizing that is wrong.
   */
  cogDistance: number | null;
  /**
   * Dynamic moves only: how settled the CoM is just after the target hold is
   * caught (mean CoM speed over the landing window, normalized units/second).
   * Smaller = more controlled landing. Null for static moves.
   */
  landingControl: number | null;
  /** Mean pose confidence over the move's frames, 0..1. */
  confidence: number;
  /** True when confidence is below the scoring threshold; downstream describes
   *  the move as low-confidence instead of giving a confident correction. */
  lowConfidence: boolean;
  /** Frame window of the move, inclusive on both ends. */
  startFrame: number;
  endFrame: number;
}
