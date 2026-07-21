import { type FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { login, useAuth } from '../store/auth';
import { ApiError } from '../services/api';

export default function Login() {
  const user = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-container">
      <h1>Sign in</h1>
      <p className="muted">Analyze your climbs and get per-move technique feedback.</p>
      <form className="card" onSubmit={onSubmit}>
        {error && <div className="error">{error}</div>}
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button className="primary" type="submit" disabled={busy} style={{ width: '100%' }}>
          {busy ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
      <p className="muted" style={{ textAlign: 'center', marginTop: 14 }}>
        No account? <Link to="/signup">Create one</Link>
      </p>
    </div>
  );
}
