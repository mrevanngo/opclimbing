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
        <button className="primary" onClick={() => navigate('/upload')}>
          Upload a climb
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {climbs === null && <p className="muted">Loading...</p>}

      {climbs !== null && climbs.length === 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <p className="muted" style={{ margin: 0 }}>
            No climbs yet. Upload a video to get per-move technique feedback.
          </p>
        </div>
      )}

      {climbs !== null && climbs.length > 0 && (
        <div className="climb-list" style={{ marginTop: 16 }}>
          {climbs.map((c) => (
            <div className="card climb-card" key={c.id}>
              <div style={{ flex: 1 }}>
                <div>
                  <Link to={`/climb/${c.id}`}>Climb {new Date(c.created_at).toLocaleString()}</Link>
                </div>
                <span className={`badge ${c.status}`}>{c.status}</span>
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
