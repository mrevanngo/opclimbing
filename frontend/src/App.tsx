// DEV VERIFICATION HARNESS - not the product Upload screen (that is Phase 2).
// This page exercises the real client pipeline (pose.ts -> cog.ts) in a browser
// on the fixture clip, to close out the pose.ts checklist item: prove the
// in-browser MediaPipe Tasks extraction + seek loop works end-to-end and agrees
// with the committed landmark fixture. main.tsx will replace this with the
// router when Phase 2 starts.

import { useEffect, useRef, useState } from 'react';
import { extractLandmarks, DEFAULT_SAMPLE_FPS } from './pipeline/pose';
import { computeCoGTrajectory, computeFrameCoG } from './pipeline/cog';
import type { FrameLandmarks, PoseResult } from './pipeline/types';

const CLIP_URL = '/clip-01.mp4';
const FIXTURE_URL = '/clip-01.landmarks.json';
const OVERLAY_TIME = 6; // seconds - a mid-climb frame to overlay the skeleton on

interface CrossCheck {
  comparedFrames: number;
  meanDx: number;
  meanDy: number;
  maxDx: number;
  maxDy: number;
}

interface Stats {
  frames: number;
  detectedPct: number;
  meanConfidence: number;
  minConfidence: number;
  elapsedMs: number;
  crossCheck: CrossCheck | null;
}

function loadVideo(video: HTMLVideoElement, src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const onReady = (): void => {
      if (Number.isFinite(video.duration) && video.duration > 0) {
        cleanup();
        resolve();
      }
    };
    const onError = (): void => {
      cleanup();
      reject(new Error(`failed to load video ${src}`));
    };
    const cleanup = (): void => {
      video.removeEventListener('loadedmetadata', onReady);
      video.removeEventListener('error', onError);
    };
    video.addEventListener('loadedmetadata', onReady);
    video.addEventListener('error', onError);
    video.src = src;
    video.load();
  });
}

function seek(video: HTMLVideoElement, t: number): Promise<void> {
  return new Promise((resolve) => {
    const onSeeked = (): void => {
      video.removeEventListener('seeked', onSeeked);
      resolve();
    };
    video.addEventListener('seeked', onSeeked);
    video.currentTime = t;
  });
}

// MediaPipe Pose skeleton edges (subset: torso, arms, legs) for a legible overlay.
const EDGES: [number, number][] = [
  [11, 12], [11, 23], [12, 24], [23, 24], // torso
  [11, 13], [13, 15], [12, 14], [14, 16], // arms
  [23, 25], [25, 27], [24, 26], [26, 28], // legs
];

async function drawOverlay(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
  pose: PoseResult,
  time: number,
): Promise<void> {
  await seek(video, time);
  const w = video.videoWidth;
  const h = video.videoHeight;
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.drawImage(video, 0, 0, w, h);

  const idx = Math.min(Math.round(time * pose.frameRate), pose.frames.length - 1);
  const frame = pose.frames[idx];

  ctx.strokeStyle = 'rgba(0,220,255,0.9)';
  ctx.lineWidth = 3;
  for (const [a, b] of EDGES) {
    ctx.beginPath();
    ctx.moveTo(frame[a].x * w, frame[a].y * h);
    ctx.lineTo(frame[b].x * w, frame[b].y * h);
    ctx.stroke();
  }
  ctx.fillStyle = 'rgba(0,220,255,0.9)';
  for (const lm of frame) {
    ctx.beginPath();
    ctx.arc(lm.x * w, lm.y * h, 4, 0, Math.PI * 2);
    ctx.fill();
  }
  // The computed center of mass (exercises cog.ts in the browser too).
  const cog = computeFrameCoG(frame);
  ctx.fillStyle = 'rgba(255,60,60,0.95)';
  ctx.beginPath();
  ctx.arc(cog.x * w, cog.y * h, 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = 'white';
  ctx.lineWidth = 2;
  ctx.stroke();
}

async function crossCheckFixture(pose: PoseResult): Promise<CrossCheck | null> {
  const resp = await fetch(FIXTURE_URL);
  if (!resp.ok) return null;
  const fixture = (await resp.json()) as { frames: FrameLandmarks[] };
  const n = Math.min(pose.frames.length, fixture.frames.length);
  let sumDx = 0;
  let sumDy = 0;
  let maxDx = 0;
  let maxDy = 0;
  let count = 0;
  for (let f = 0; f < n; f++) {
    for (let i = 0; i < 33; i++) {
      const a = pose.frames[f][i];
      const b = fixture.frames[f][i];
      if (b.visibility < 0.5) continue; // only compare landmarks the fixture trusts
      const dx = Math.abs(a.x - b.x);
      const dy = Math.abs(a.y - b.y);
      sumDx += dx;
      sumDy += dy;
      maxDx = Math.max(maxDx, dx);
      maxDy = Math.max(maxDy, dy);
      count++;
    }
  }
  if (count === 0) return null;
  return { comparedFrames: n, meanDx: sumDx / count, meanDy: sumDy / count, maxDx, maxDy };
}

function App() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [status, setStatus] = useState('starting');
  const [progress, setProgress] = useState(0);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // guard StrictMode double-invoke
    started.current = true;
    void run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function run(): Promise<void> {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    try {
      setError(null);
      setStats(null);
      setStatus('loading video + MediaPipe model (WASM)');
      await loadVideo(video, CLIP_URL);

      setStatus('extracting landmarks in-browser');
      const t0 = performance.now();
      const pose = await extractLandmarks(video, DEFAULT_SAMPLE_FPS, setProgress);
      const elapsedMs = performance.now() - t0;

      setStatus('scoring center of mass + cross-checking fixture');
      const trajectory = computeCoGTrajectory(pose.frames);
      const confs = trajectory.map((p) => p.confidence);
      const detected = pose.frames.filter((f) => f.some((l) => l.visibility > 0)).length;
      await drawOverlay(video, canvas, pose, OVERLAY_TIME);
      const crossCheck = await crossCheckFixture(pose);

      setStats({
        frames: pose.frames.length,
        detectedPct: (detected / pose.frames.length) * 100,
        meanConfidence: confs.reduce((s, v) => s + v, 0) / confs.length,
        minConfidence: Math.min(...confs),
        elapsedMs,
        crossCheck,
      });
      setStatus('done');
    } catch (e) {
      setError(e instanceof Error ? `${e.message}\n${e.stack ?? ''}` : String(e));
      setStatus('error');
    }
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: 24, maxWidth: 1000, margin: '0 auto' }}>
      <h1 style={{ fontSize: 20 }}>pose.ts browser verification - clip-01</h1>
      <p data-testid="status">
        <strong>Status:</strong> {status}
        {status.startsWith('extracting') && ` (${(progress * 100).toFixed(0)}%)`}
      </p>

      {error && (
        <pre
          data-testid="error"
          style={{ color: '#b00', whiteSpace: 'pre-wrap', background: '#fee', padding: 12, borderRadius: 6 }}
        >
          {error}
        </pre>
      )}

      {stats && (
        <table data-testid="stats" style={{ borderCollapse: 'collapse', margin: '12px 0' }}>
          <tbody>
            {[
              ['Frames extracted', String(stats.frames)],
              ['Person detected', `${stats.detectedPct.toFixed(1)}%`],
              ['Mean CoM confidence', stats.meanConfidence.toFixed(3)],
              ['Min CoM confidence', stats.minConfidence.toFixed(3)],
              ['Extraction time', `${(stats.elapsedMs / 1000).toFixed(1)}s`],
              [
                'Cross-check vs fixture (mean |Δx|, |Δy|)',
                stats.crossCheck
                  ? `${stats.crossCheck.meanDx.toFixed(4)}, ${stats.crossCheck.meanDy.toFixed(4)} ` +
                    `over ${stats.crossCheck.comparedFrames} frames (max ${stats.crossCheck.maxDx.toFixed(3)}, ${stats.crossCheck.maxDy.toFixed(3)})`
                  : 'fixture not found',
              ],
            ].map(([k, v]) => (
              <tr key={k}>
                <td style={{ border: '1px solid #ccc', padding: '4px 10px', fontWeight: 600 }}>{k}</td>
                <td style={{ border: '1px solid #ccc', padding: '4px 10px' }}>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <p style={{ color: '#555', fontSize: 13 }}>
        Skeleton (cyan) and computed center of mass (red) overlaid on the frame at {OVERLAY_TIME}s:
      </p>
      <canvas ref={canvasRef} data-testid="overlay" style={{ maxHeight: 460, border: '1px solid #ccc' }} />
      {/* Hidden source video the pipeline reads from. */}
      <video ref={videoRef} muted playsInline preload="auto" style={{ display: 'none' }} />
    </div>
  );
}

export default App;
