import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import * as api from '../services/api';
import type { Climb } from '../services/api';
import { clearAuth } from '../store/auth';

export default function Home() {
  const navigate = useNavigate();
  const [climbs, setClimbs] = useState<Climb[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh(): Promise<void> {
    try {
      const { climbs } = await api.listClimbs();
      setClimbs(climbs);
    } catch (err) {
      if (err instanceof api.ApiError && err.status === 401) {
        clearAuth();
        return;
      }
      setError(err instanceof api.ApiError ? err.message : 'Failed to load climbs');
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onDelete(id: string): Promise<void> {
    try {
      await api.deleteClimb(id);
      setClimbs((prev) => (prev ? prev.filter((c) => c.id !== id) : prev));
    } catch (err) {
      setError(err instanceof api.ApiError ? err.message : 'Delete failed');
    }
  }

  return (
    <div className="container">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h1>Your climbs</h1>
        <div className="row" style={{ gap: 8 }}>
          <button onClick={() => navigate('/progress')}>Progress</button>
          <button onClick={() => navigate('/upload')}>Upload video</button>
          <button className="primary" onClick={() => navigate('/log')}>
            Log a climb
          </button>
        </div>
      </div>

      {error && <div className="error">{error}</div>}

      {climbs === null && <p className="muted">Loading...</p>}

      {climbs !== null && climbs.length === 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <p className="muted" style={{ margin: 0 }}>
            No climbs yet. <Link to="/log">Log a climb</Link> to start tracking your progress, or{' '}
            <Link to="/upload">upload a video</Link> for per-move technique feedback.
          </p>
        </div>
      )}

      {climbs !== null && climbs.length > 0 && (
        <div className="climb-list" style={{ marginTop: 16 }}>
          {climbs.map((c) => (
            <div className="card climb-card" key={c.id}>
              <div style={{ flex: 1 }}>
                <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
                  {c.grade !== null && <strong>V{c.grade}</strong>}
                  {c.angle && <span className="badge">{c.angle}</span>}
                  {c.outcome && (
                    <span className={`badge outcome-${c.outcome}`}>
                      {c.outcome === 'attempt' ? 'did not send' : c.outcome}
                    </span>
                  )}
                  {c.status === 'analyzed' && <span className="badge analyzed">analyzed</span>}
                </div>
                <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                  {new Date(c.climbed_at ?? c.created_at).toLocaleDateString()}
                  {c.hold_types.length > 0 && <> - {c.hold_types.join(', ')}</>}
                </div>
                {c.beta_notes && (
                  <div style={{ fontSize: 13, marginTop: 4 }}>{c.beta_notes}</div>
                )}
                {c.status === 'analyzed' && (
                  <Link to={`/climb/${c.id}`} style={{ fontSize: 13 }}>
                    View move-by-move feedback
                  </Link>
                )}
              </div>
              <button className="danger" onClick={() => onDelete(c.id)}>
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
