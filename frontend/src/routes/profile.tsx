import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { logout, useAuth } from '../store/auth';

export default function Profile() {
  const user = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  async function onSignOut(): Promise<void> {
    setBusy(true);
    await logout();
    navigate('/login');
  }

  return (
    <div className="container">
      <h1>Profile</h1>
      <div className="card">
        <div className="field">
          <label>Name</label>
          <div>{user?.name}</div>
        </div>
        <div className="field">
          <label>Email</label>
          <div>{user?.email}</div>
        </div>
        <div className="field">
          <label>Member since</label>
          <div>{user ? new Date(user.created_at).toLocaleDateString() : ''}</div>
        </div>
        <button className="danger" onClick={onSignOut} disabled={busy}>
          {busy ? 'Signing out...' : 'Sign out'}
        </button>
      </div>
    </div>
  );
}
