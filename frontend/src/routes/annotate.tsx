import { type MouseEvent, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import * as api from '../services/api';
import { clearDraft, getDraft } from '../store/draft';
import type { Hold } from '../pipeline/types';

export default function Annotate() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const draft = id ? getDraft(id) : null;
  const [holds, setHolds] = useState<Hold[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  if (!id || !draft) {
    return (
      <div className="container">
        <h1>Annotate holds</h1>
        <div className="card">
          <p className="muted">
            This climb's frames are no longer in memory (the page was reloaded). Please{' '}
            <Link to="/upload">upload the video again</Link>.
          </p>
        </div>
      </div>
    );
  }

  function onStageClick(e: MouseEvent<HTMLImageElement>): void {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height));
    setHolds((prev) => [...prev, { sequenceIndex: prev.length, frameX: x, frameY: y }]);
  }

  function undo(): void {
    setHolds((prev) => prev.slice(0, -1));
  }
  function clearAll(): void {
    setHolds([]);
  }

  async function submit(): Promise<void> {
    if (holds.length === 0) {
      setError('Tap at least one hold, in the order you use them.');
      return;
    }
    setError(null);
    try {
      const climbId = id!;
      const stableDraft = draft!;
      setBusy('Saving holds...');
      await api.putHolds(climbId, api.holdsToPayload(holds));
      setBusy('Analyzing your technique...');
      await api.analyze(climbId, stableDraft.landmarks, stableDraft.frameRate);
      clearDraft();
      navigate(`/climb/${climbId}`);
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : 'Analysis failed');
      setBusy(null);
    }
  }

  return (
    <div className="container">
      <h1>Tap the holds in order</h1>
      <p className="muted">
        Click each hold in the sequence you use it (start hold first). This is how the app knows the
        intended route.
      </p>

      {error && <div className="error">{error}</div>}

      <div className="row" style={{ gap: 8, marginBottom: 12 }}>
        <button onClick={undo} disabled={holds.length === 0 || busy !== null}>
          Undo
        </button>
        <button onClick={clearAll} disabled={holds.length === 0 || busy !== null}>
          Clear
        </button>
        <span className="muted">{holds.length} hold(s)</span>
        <div className="spacer" style={{ flex: 1 }} />
        <button className="primary" onClick={submit} disabled={busy !== null}>
          {busy ?? 'Analyze'}
        </button>
      </div>

      <div className="annotate-stage">
        <img src={draft.frameDataUrl} alt="climb frame" onClick={onStageClick} draggable={false} />
        {holds.map((h) => (
          <div
            key={h.sequenceIndex}
            className="hold-marker"
            style={{ left: `${h.frameX * 100}%`, top: `${h.frameY * 100}%` }}
          >
            {h.sequenceIndex + 1}
          </div>
        ))}
      </div>
    </div>
  );
}
