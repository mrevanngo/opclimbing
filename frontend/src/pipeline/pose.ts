// Stage 1 - pose estimation (PIPELINE.md). Settled Decision: in-browser MediaPipe
// Tasks Pose Landmarker (WASM), NOT server-side. Raw video never leaves the device;
// only extracted landmarks move on through the pipeline.

import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision';
import type { FrameLandmarks, Landmark, PoseResult } from './types';

// MediaPipe ships its WASM runtime and model as separate assets. Pinned versions,
// not "latest", so extraction is reproducible against the saved fixtures.
const WASM_BASE_URL = 'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14/wasm';
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/1/pose_landmarker_full.task';

export const LANDMARKS_PER_FRAME = 33;

/** Default sampling rate for extraction. Phone video is 30 or 60 fps; 30 is
 *  plenty for CoM velocity/acceleration and halves the extraction work. */
export const DEFAULT_SAMPLE_FPS = 30;

let landmarkerPromise: Promise<PoseLandmarker> | null = null;

/** Lazily create the PoseLandmarker once and reuse it across extractions. */
function getLandmarker(): Promise<PoseLandmarker> {
  if (landmarkerPromise === null) {
    landmarkerPromise = (async () => {
      const vision = await FilesetResolver.forVisionTasks(WASM_BASE_URL);
      return PoseLandmarker.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
        runningMode: 'VIDEO',
        numPoses: 1,
      });
    })();
  }
  return landmarkerPromise;
}

/** A frame where no person was detected: 33 landmarks with zero visibility, so
 *  downstream confidence goes to zero instead of the frame being silently skipped
 *  (which would corrupt the time base that velocity depends on). */
function emptyFrame(): FrameLandmarks {
  return Array.from({ length: LANDMARKS_PER_FRAME }, (): Landmark => ({
    x: 0,
    y: 0,
    z: 0,
    visibility: 0,
  }));
}

function seekTo(video: HTMLVideoElement, time: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const onSeeked = (): void => {
      video.removeEventListener('seeked', onSeeked);
      video.removeEventListener('error', onError);
      resolve();
    };
    const onError = (): void => {
      video.removeEventListener('seeked', onSeeked);
      video.removeEventListener('error', onError);
      reject(new Error(`failed to seek video to ${time}s`));
    };
    video.addEventListener('seeked', onSeeked);
    video.addEventListener('error', onError);
    video.currentTime = time;
  });
}

/**
 * Extract per-frame pose landmarks from a loaded video element by stepping
 * through it at `sampleFps`. Deterministic seek-and-detect (rather than
 * playback-driven capture) so the same clip always yields the same frames -
 * which the regression fixtures depend on.
 *
 * Returns normalized landmarks with visibility per frame plus the sample rate;
 * later stages need the rate to compute real-time velocity. The `z` values are
 * carried through but are unreliable and never scored (Settled Decision).
 */
export async function extractLandmarks(
  video: HTMLVideoElement,
  sampleFps: number = DEFAULT_SAMPLE_FPS,
  onProgress?: (fraction: number) => void,
): Promise<PoseResult> {
  if (!Number.isFinite(video.duration) || video.duration <= 0) {
    throw new Error('video has no duration - is it loaded? (call after loadedmetadata)');
  }
  if (sampleFps <= 0) {
    throw new Error(`sampleFps must be positive, got ${sampleFps}`);
  }

  const landmarker = await getLandmarker();
  const dt = 1 / sampleFps;
  const frames: FrameLandmarks[] = [];

  for (let t = 0; t < video.duration; t += dt) {
    await seekTo(video, t);
    const result = landmarker.detectForVideo(video, Math.round(t * 1000));
    const pose = result.landmarks[0];
    if (pose === undefined || pose.length !== LANDMARKS_PER_FRAME) {
      frames.push(emptyFrame());
    } else {
      frames.push(
        pose.map((lm): Landmark => ({
          x: lm.x,
          y: lm.y,
          z: lm.z,
          visibility: lm.visibility ?? 0,
        })),
      );
    }
    onProgress?.(Math.min(1, (t + dt) / video.duration));
  }

  return { frameRate: sampleFps, frames };
}
