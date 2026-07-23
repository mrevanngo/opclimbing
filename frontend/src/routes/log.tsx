import { type FormEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import * as api from '../services/api';
import type { Angle, HoldType, Outcome } from '../services/api';

/** Log a climb. No video required: most logged climbs are just an entry, and
 *  these fields are what the progression analytics are built from. */
export default function LogClimb() {
  const navigate = useNavigate();
  const [grade, setGrade] = useState(3);
  const [angle, setAngle] = useState<Angle>('vertical');
  const [outcome, setOutcome] = useState<Outcome>('send');
  const [attempts, setAttempts] = useState(1);
  const [holdTypes, setHoldTypes] = useState<HoldType[]>([]);
  const [notes, setNotes] = useState('');
  const [climbedAt, setClimbedAt] = useState(() => new Date().toISOString().slice(0, 10));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function toggleHold(h: HoldType): void {
    setHoldTypes((prev) => (prev.includes(h) ? prev.filter((x) => x !== h) : [...prev, h]));
  }

  async function onSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.createClimb({
        grade,
        angle,
        outcome,
        attempts,
        hold_types: holdTypes,
        beta_notes: notes.trim() || null,
        // Send as UTC instant so the API stores a proper timestamp.
        climbed_at: new Date(`${climbedAt}T12:00:00`).toISOString(),
      });
      navigate('/');
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : 'Could not log this climb');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="container">
      <h1>Log a climb</h1>
      <p className="muted">
        Every logged climb feeds your progression stats. A video is optional.
      </p>

      {error && <div className="error">{error}</div>}

      <form className="card" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="grade">Grade (V{grade})</label>
          <input
            id="grade"
            type="range"
            min={0}
            max={17}
            value={grade}
            onChange={(e) => setGrade(Number(e.target.value))}
          />
        </div>

        <div className="field">
          <label>Wall angle</label>
          <div className="chips">
            {api.ANGLES.map((a) => (
              <button
                key={a}
                type="button"
                className={`chip ${angle === a ? 'on' : ''}`}
                onClick={() => setAngle(a)}
              >
                {a}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>Outcome</label>
          <div className="chips">
            {api.OUTCOMES.map((o) => (
              <button
                key={o}
                type="button"
                className={`chip ${outcome === o ? 'on' : ''}`}
                onClick={() => setOutcome(o)}
              >
                {o === 'attempt' ? 'did not send' : o}
              </button>
            ))}
          </div>
        </div>

        <div className="field">
          <label>Hold types on this climb</label>
          <div className="chips">
            {api.HOLD_TYPES.map((h) => (
              <button
                key={h}
                type="button"
                className={`chip ${holdTypes.includes(h) ? 'on' : ''}`}
                onClick={() => toggleHold(h)}
              >
                {h}
              </button>
            ))}
          </div>
        </div>

        <div className="row" style={{ gap: 12 }}>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="attempts">Attempts</label>
            <input
              id="attempts"
              type="number"
              min={1}
              value={attempts}
              onChange={(e) => setAttempts(Math.max(1, Number(e.target.value)))}
            />
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label htmlFor="date">Date climbed</label>
            <input
              id="date"
              type="date"
              value={climbedAt}
              onChange={(e) => setClimbedAt(e.target.value)}
            />
          </div>
        </div>

        <div className="field">
          <label htmlFor="notes">Beta notes</label>
          <input
            id="notes"
            placeholder="heel hook on the arete, long move to the sloper..."
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>

        <button className="primary" type="submit" disabled={busy} data-testid="save-climb">
          {busy ? 'Saving...' : 'Log climb'}
        </button>
      </form>
    </div>
  );
}
