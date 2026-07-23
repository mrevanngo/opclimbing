import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import * as api from '../services/api';
import type { AngleStat, HoldTypeStat, ProgressionPoint } from '../services/api';

const TREND_LABEL: Record<AngleStat['trend'], string> = {
  improving: 'improving',
  plateau: 'plateau',
  declining: 'declining',
  insufficient_data: 'not enough data',
};

/** Grade progression over time: running best as a line, each month's hardest
 *  send as a point. Hand-drawn SVG to avoid a charting dependency. */
function ProgressionChart({ points }: { points: ProgressionPoint[] }) {
  const W = 640;
  const H = 220;
  const PAD = 34;

  const grades = points.flatMap((p) => [p.running_best, p.max_grade]);
  const min = Math.min(...grades);
  const max = Math.max(...grades);
  const span = Math.max(1, max - min);

  const x = (i: number): number =>
    points.length === 1 ? W / 2 : PAD + (i * (W - 2 * PAD)) / (points.length - 1);
  const y = (g: number): number => H - PAD - ((g - min) / span) * (H - 2 * PAD);

  const line = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(p.running_best)}`).join(' ');

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Grade progression">
      {/* grade gridlines */}
      {Array.from({ length: span + 1 }, (_, k) => min + k).map((g) => (
        <g key={g}>
          <line x1={PAD} x2={W - PAD} y1={y(g)} y2={y(g)} stroke="#2a2f3a" strokeWidth={1} />
          <text x={8} y={y(g) + 4} fill="#9aa3b2" fontSize={11}>
            V{g}
          </text>
        </g>
      ))}
      <path d={line} fill="none" stroke="#4f9dff" strokeWidth={2.5} />
      {points.map((p, i) => (
        <g key={p.month}>
          <circle cx={x(i)} cy={y(p.max_grade)} r={4} fill="#35c07f" />
          <text x={x(i)} y={H - 10} fill="#9aa3b2" fontSize={11} textAnchor="middle">
            {p.month.slice(2)}
          </text>
        </g>
      ))}
    </svg>
  );
}

export default function Progress() {
  const [progression, setProgression] = useState<ProgressionPoint[] | null>(null);
  const [holdTypes, setHoldTypes] = useState<HoldTypeStat[]>([]);
  const [angles, setAngles] = useState<AngleStat[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const [p, h, a] = await Promise.all([
          api.getProgression(),
          api.getHoldTypeStats(),
          api.getAngleStats(),
        ]);
        setProgression(p.progression);
        setHoldTypes(h.hold_types);
        setAngles(a.angles);
      } catch (err) {
        setError(err instanceof api.ApiError ? err.message : 'Could not load your stats');
      }
    })();
  }, []);

  if (error) {
    return (
      <div className="container">
        <div className="error">{error}</div>
      </div>
    );
  }

  if (progression === null) {
    return (
      <div className="container">
        <p className="muted">Loading your progress...</p>
      </div>
    );
  }

  const hasData = progression.length > 0 || angles.length > 0;

  return (
    <div className="container">
      <h1>Progress</h1>

      {!hasData && (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            No logged climbs yet. <Link to="/log">Log a climb</Link> and your grade progression,
            strongest and weakest hold types, and per-angle trends will appear here.
          </p>
        </div>
      )}

      {progression.length > 0 && (
        <section className="card" style={{ marginBottom: 18 }}>
          <h2>Grade progression</h2>
          <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
            Blue line is your best grade sent to date. Green dots are each month's hardest send.
          </p>
          <ProgressionChart points={progression} />
        </section>
      )}

      {angles.length > 0 && (
        <section className="card" style={{ marginBottom: 18 }}>
          <h2>By wall angle</h2>
          <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
            Trend is the slope of your sent grades over time, so a flat slope is a plateau.
          </p>
          {angles.map((a) => (
            <div className="stat-row" key={a.angle} data-testid={`angle-${a.angle}`}>
              <div className="stat-head">
                <strong style={{ textTransform: 'capitalize' }}>{a.angle}</strong>
                <span className={`trend ${a.trend}`}>{TREND_LABEL[a.trend]}</span>
                {a.grade_per_month !== null && a.trend !== 'insufficient_data' && (
                  <span className="muted" style={{ fontSize: 12 }}>
                    {a.grade_per_month > 0 ? '+' : ''}
                    {a.grade_per_month} grades/month
                  </span>
                )}
              </div>
              <div className="bar">
                <div style={{ width: `${a.send_rate}%` }} />
              </div>
              <div className="muted" style={{ fontSize: 13 }}>
                {a.sends}/{a.logged} sent ({a.send_rate}%)
                {a.best_grade !== null && <> - best V{a.best_grade}</>}
              </div>
            </div>
          ))}
        </section>
      )}

      {holdTypes.length > 0 && (
        <section className="card">
          <h2>By hold type</h2>
          <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
            Weakest first. Low counts are noisy, so check the sample size.
          </p>
          {holdTypes.map((h) => (
            <div className="stat-row" key={h.hold_type} data-testid={`hold-${h.hold_type}`}>
              <div className="stat-head">
                <strong style={{ textTransform: 'capitalize' }}>{h.hold_type}</strong>
                <span className="muted" style={{ fontSize: 13 }}>
                  {h.sends}/{h.total} sent ({h.send_rate}%)
                </span>
              </div>
              <div className="bar">
                <div style={{ width: `${h.send_rate}%` }} />
              </div>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
