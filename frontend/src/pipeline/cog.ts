// Stage 2 - segmental, mass-weighted center of mass (PIPELINE.md, Settled Decision).
// NOT the hip-midpoint shortcut: the hip midpoint is wrong exactly when the arms are
// overhead, which is most of climbing. Standard Dempster anthropometric values.

import type { CoGPoint, FrameLandmarks, Landmark, Point2D } from './types';

// MediaPipe Pose landmark indices (verified against @mediapipe/tasks-vision 0.10.x docs).
export const LANDMARK = {
  LEFT_SHOULDER: 11,
  RIGHT_SHOULDER: 12,
  LEFT_ELBOW: 13,
  RIGHT_ELBOW: 14,
  LEFT_WRIST: 15,
  RIGHT_WRIST: 16,
  LEFT_HIP: 23,
  RIGHT_HIP: 24,
  LEFT_KNEE: 25,
  RIGHT_KNEE: 26,
  LEFT_ANKLE: 27,
  RIGHT_ANKLE: 28,
} as const;

/**
 * A body segment: a fraction of total body mass located at a fixed fraction of
 * the distance from its proximal to its distal endpoint. Point-approximated
 * segments (head, hands, feet) use the same endpoint twice.
 */
interface Segment {
  name: string;
  massFraction: number;
  /** CoM location as a fraction of the way from proximal to distal endpoint. */
  comFraction: number;
  /** Landmark indices; a two-index midpoint is encoded as a pair. */
  proximal: number | [number, number];
  distal: number | [number, number];
}

const SHOULDER_MID: [number, number] = [LANDMARK.LEFT_SHOULDER, LANDMARK.RIGHT_SHOULDER];
const HIP_MID: [number, number] = [LANDMARK.LEFT_HIP, LANDMARK.RIGHT_HIP];

// Dempster mass fractions (PIPELINE.md table). Paired-limb fractions are PER SIDE.
export const SEGMENTS: Segment[] = [
  // Head + neck approximated as a point at the shoulder midpoint (PIPELINE.md).
  { name: 'head_neck', massFraction: 0.081, comFraction: 0, proximal: SHOULDER_MID, distal: SHOULDER_MID },
  // Trunk dominates the total, so its endpoints matter most.
  { name: 'trunk', massFraction: 0.497, comFraction: 0.5, proximal: SHOULDER_MID, distal: HIP_MID },
  { name: 'upper_arm_l', massFraction: 0.028, comFraction: 0.436, proximal: LANDMARK.LEFT_SHOULDER, distal: LANDMARK.LEFT_ELBOW },
  { name: 'upper_arm_r', massFraction: 0.028, comFraction: 0.436, proximal: LANDMARK.RIGHT_SHOULDER, distal: LANDMARK.RIGHT_ELBOW },
  { name: 'forearm_l', massFraction: 0.016, comFraction: 0.43, proximal: LANDMARK.LEFT_ELBOW, distal: LANDMARK.LEFT_WRIST },
  { name: 'forearm_r', massFraction: 0.016, comFraction: 0.43, proximal: LANDMARK.RIGHT_ELBOW, distal: LANDMARK.RIGHT_WRIST },
  // Hands approximated as points at the wrists.
  { name: 'hand_l', massFraction: 0.006, comFraction: 0, proximal: LANDMARK.LEFT_WRIST, distal: LANDMARK.LEFT_WRIST },
  { name: 'hand_r', massFraction: 0.006, comFraction: 0, proximal: LANDMARK.RIGHT_WRIST, distal: LANDMARK.RIGHT_WRIST },
  { name: 'thigh_l', massFraction: 0.1, comFraction: 0.433, proximal: LANDMARK.LEFT_HIP, distal: LANDMARK.LEFT_KNEE },
  { name: 'thigh_r', massFraction: 0.1, comFraction: 0.433, proximal: LANDMARK.RIGHT_HIP, distal: LANDMARK.RIGHT_KNEE },
  { name: 'shank_l', massFraction: 0.0465, comFraction: 0.433, proximal: LANDMARK.LEFT_KNEE, distal: LANDMARK.LEFT_ANKLE },
  { name: 'shank_r', massFraction: 0.0465, comFraction: 0.433, proximal: LANDMARK.RIGHT_KNEE, distal: LANDMARK.RIGHT_ANKLE },
  // Feet approximated as points at the ankles.
  { name: 'foot_l', massFraction: 0.0145, comFraction: 0, proximal: LANDMARK.LEFT_ANKLE, distal: LANDMARK.LEFT_ANKLE },
  { name: 'foot_r', massFraction: 0.0145, comFraction: 0, proximal: LANDMARK.RIGHT_ANKLE, distal: LANDMARK.RIGHT_ANKLE },
];

/** Sum of all segment mass fractions. The cheapest correctness check in the
 *  pipeline: this must be ~1.0 or a segment is missing or double-counted. */
export function totalMassFraction(): number {
  return SEGMENTS.reduce((sum, s) => sum + s.massFraction, 0);
}

if (Math.abs(totalMassFraction() - 1.0) > 1e-6) {
  throw new Error(
    `Segment mass fractions sum to ${totalMassFraction()}, expected 1.0 - ` +
      'a segment is missing or double-counted (see PIPELINE.md Stage 2)',
  );
}

/** Landmark indices the CoM model depends on (for per-frame confidence). */
export const COG_LANDMARK_INDICES: number[] = Object.values(LANDMARK);

function resolvePoint(frame: FrameLandmarks, ref: number | [number, number]): Point2D {
  if (typeof ref === 'number') {
    const lm = frame[ref];
    return { x: lm.x, y: lm.y };
  }
  const a = frame[ref[0]];
  const b = frame[ref[1]];
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

/**
 * Compute the whole-body center of mass for one frame: each segment's CoM point
 * weighted by its mass fraction, summed, divided by the total mass fraction.
 * Confidence is the mean visibility of the landmarks the model uses; a
 * low-visibility endpoint makes the frame lower-confidence rather than being
 * silently trusted.
 */
export function computeFrameCoG(frame: FrameLandmarks): CoGPoint {
  let x = 0;
  let y = 0;
  let mass = 0;
  for (const segment of SEGMENTS) {
    const p = resolvePoint(frame, segment.proximal);
    const d = resolvePoint(frame, segment.distal);
    const comX = p.x + (d.x - p.x) * segment.comFraction;
    const comY = p.y + (d.y - p.y) * segment.comFraction;
    x += comX * segment.massFraction;
    y += comY * segment.massFraction;
    mass += segment.massFraction;
  }

  const visibilities = COG_LANDMARK_INDICES.map((i) => frame[i].visibility);
  const confidence = visibilities.reduce((s, v) => s + v, 0) / visibilities.length;

  return { x: x / mass, y: y / mass, confidence };
}

/** Compute the CoM trajectory for a whole clip: one CoGPoint per frame. */
export function computeCoGTrajectory(frames: FrameLandmarks[]): CoGPoint[] {
  return frames.map(computeFrameCoG);
}

/** Guard against frames that do not carry the full 33-landmark set. */
export function isCompleteFrame(frame: FrameLandmarks): frame is Landmark[] {
  return frame.length === 33;
}
