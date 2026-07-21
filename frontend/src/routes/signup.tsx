import { type FormEvent, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { signup, useAuth } from '../store/auth';
import { ApiError } from '../services/api';

export default function Signup() {
  const user = useAuth();
  const navigate = useNavigate();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function onSubmit(e: FormEvent): Promise<void> {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    setBusy(true);
    try {
      await signup(name, email, password);
      navigate('/');
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Signup failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-container">
      <h1>Create account</h1>
      <form className="card" onSubmit={onSubmit}>
        {error && <div className="error">{error}</div>}
        <div className="field">
          <label htmlFor="name">Name</label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Password (min 8 characters)</label>
          <input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <button className="primary" type="submit" disabled={busy} style={{ width: '100%' }}>
          {busy ? 'Creating...' : 'Create account'}
        </button>
      </form>
      <p className="muted" style={{ textAlign: 'center', marginTop: 14 }}>
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </div>
  );
}
