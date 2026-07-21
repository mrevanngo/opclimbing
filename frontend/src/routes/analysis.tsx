import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import * as api from '../services/api';
import type { Analysis as AnalysisT, Move } from '../services/api';

export default function Analysis() {
  const { id } = useParams<{ id: string }>();
  const [analysis, setAnalysis] = useState<AnalysisT | null>(null);
  const [moves, setMoves] = useState<Move[]>([]);
  const [state, setState] = useState<'loading' | 'ready' | 'none' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    void (async () => {
      try {
        const data = await api.getAnalysis(id);
        setAnalysis(data.analysis);
        setMoves(data.moves);
        setState('ready');
      } catch (err) {
        if (err instanceof api.ApiError && err.status === 404) {
          setState('none');
          return;
        }
        setError(err instanceof api.ApiError ? err.message : 'Failed to load analysis');
        setState('error');
      }
    })();
  }, [id]);

  if (state === 'loading') {
    return (
      <div className="container">
        <p className="muted">Loading analysis...</p>
      </div>
    );
  }

  if (state === 'none') {
    return (
      <div className="container">
        <h1>Not analyzed yet</h1>
        <div className="card">
          <p className="muted">
            This climb has no analysis. <Link to="/upload">Upload a video</Link> to analyze a climb.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <h1>Per-move feedback</h1>
      {error && <div className="error">{error}</div>}

      {/* Per-move breakdown is the product; the summary is secondary. */}
      <div style={{ marginTop: 12 }}>
        {moves.map((m) => (
          <div className="move" key={m.move_index}>
            <div className="move-head">
              <strong>Move {m.move_index + 1}</strong>
              <span className={`move-type ${m.move_type}`}>{m.move_type}</span>
              {m.confidence < 0.5 && <span className="lowconf">low confidence</span>}
            </div>
            {m.move_type === 'static' && m.cog_distance !== null && (
              <div className="metric">
                Center of mass was {m.cog_distance.toFixed(2)} from the target hold at the reach
                (smaller = better positioned).
              </div>
            )}
            {m.move_type === 'dynamic' && (
              <div className="metric">Dynamic move - judged on landing control, not reach distance.</div>
            )}
            {m.note && <p className="note">{m.note}</p>}
          </div>
        ))}
      </div>

      {analysis?.overall_summary && (
        <div className="card" style={{ marginTop: 20 }}>
          <h2>Overall</h2>
          <p className="muted" style={{ margin: 0 }}>
            {analysis.overall_summary}
          </p>
        </div>
      )}

      <p className="muted" style={{ marginTop: 20, fontSize: 13 }}>
        Center-of-mass proximity is one lens on technique, not a full judgment of the climb. Depth
        (hips off the wall) is not measured in this version.
      </p>
    </div>
  );
}
