import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { extractLandmarks, DEFAULT_SAMPLE_FPS } from '../pipeline/pose';
import { computeCoGTrajectory } from '../pipeline/cog';
import * as api from '../services/api';
import { setDraft } from '../store/draft';

const MAX_SIZE_MB = 200;
const MAX_DURATION_S = 60;
const ACCEPTED = ['video/mp4', 'video/quicktime']; // mp4, mov

function seek(video: HTMLVideoElement, t: number): Promise<void> {
  return new Promise((resolve) => {
    const done = (): void => {
      video.removeEventListener('seeked', done);
      resolve();
    };
    video.addEventListener('seeked', done);
    video.currentTime = t;
  });
}

function loadMetadata(video: HTMLVideoElement, src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    video.onloadedmetadata = () => resolve();
    video.onerror = () => reject(new Error('Could not read this video file.'));
    video.src = src;
  });
}

export default function Upload() {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  const [status, setStatus] = useState<string>('');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onFile(file: File): Promise<void> {
    setError(null);
    if (!ACCEPTED.includes(file.type)) {
      setError('Please choose an mp4 or mov video.');
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Video is too large (limit ${MAX_SIZE_MB} MB).`);
      return;
    }

    const video = videoRef.current;
    if (!video) return;
    const url = URL.createObjectURL(file);
    setBusy(true);
    try {
      setStatus('Reading video...');
      await loadMetadata(video, url);
      if (video.duration > MAX_DURATION_S) {
        throw new Error(`Video is too long (limit ${MAX_DURATION_S}s). Trim to a single climb.`);
      }

      setStatus('Extracting pose (this runs in your browser)...');
      const pose = await extractLandmarks(video, DEFAULT_SAMPLE_FPS, setProgress);

      // Warn if the climber was barely detected - low-confidence downstream.
      const traj = computeCoGTrajectory(pose.frames);
      const meanConf = traj.reduce((s, p) => s + p.confidence, 0) / traj.length;
      if (meanConf < 0.3) {
        throw new Error('No climber was reliably detected. Try a clearer, face-on video.');
      }

      setStatus('Capturing a frame to annotate...');
      await seek(video, video.duration * 0.4);
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('Could not capture a frame.');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      const frameDataUrl = canvas.toDataURL('image/jpeg', 0.85);

      setStatus('Creating climb...');
      const { climb } = await api.createClimb();
      setDraft({
        climbId: climb.id,
        frameRate: pose.frameRate,
        landmarks: pose.frames,
        frameDataUrl,
        frameWidth: canvas.width,
        frameHeight: canvas.height,
      });
      navigate(`/climb/${climb.id}/holds`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setStatus('');
    } finally {
      URL.revokeObjectURL(url);
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <h1>Upload a climb</h1>
      <p className="muted">
        Choose a short, roughly face-on video of a single climb (mp4 or mov, up to {MAX_DURATION_S}s).
        Pose runs in your browser - the raw video never leaves your device.
      </p>

      {error && <div className="error">{error}</div>}

      <div className="card">
        <input
          type="file"
          accept="video/mp4,video/quicktime"
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void onFile(f);
          }}
        />
        {busy && (
          <div style={{ marginTop: 16 }}>
            <p className="muted">{status}</p>
            {status.startsWith('Extracting') && (
              <div className="progress">
                <div style={{ width: `${Math.round(progress * 100)}%` }} />
              </div>
            )}
          </div>
        )}
      </div>

      <video ref={videoRef} muted playsInline preload="auto" style={{ display: 'none' }} />
    </div>
  );
}
