// Transient, in-memory hand-off between Upload -> Annotate -> Analyze for one
// climb: the browser-extracted landmarks, the frame rate, and a still frame to
// annotate holds on. Not persisted - the landmarks are large and only needed
// until analysis runs. On a hard reload mid-flow the user re-uploads (V1).

import type { FrameLandmarks } from '../pipeline/types';

export interface ClimbDraft {
  climbId: string;
  frameRate: number;
  landmarks: FrameLandmarks[];
  /** A still frame (data URL) the user taps holds on. */
  frameDataUrl: string;
  frameWidth: number;
  frameHeight: number;
}

let draft: ClimbDraft | null = null;

export function setDraft(d: ClimbDraft): void {
  draft = d;
}

export function getDraft(climbId: string): ClimbDraft | null {
  return draft && draft.climbId === climbId ? draft : null;
}

export function clearDraft(): void {
  draft = null;
}
