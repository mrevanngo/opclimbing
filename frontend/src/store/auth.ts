// Auth state: the current user object only (CLAUDE.md). The session itself is
// the backend's httpOnly cookie - the token is never read or stored by JS.
// The user object is cached in localStorage (display data, NOT the token) so a
// page reload keeps showing the signed-in user while the cookie stays the source
// of truth; any 401 from the API clears it.

import { useSyncExternalStore } from 'react';
import * as api from '../services/api';
import type { User } from '../services/api';

const STORAGE_KEY = 'oc_user';

function load(): User | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

let currentUser: User | null = load();
const listeners = new Set<() => void>();

function emit(): void {
  for (const l of listeners) l();
}

function setUser(user: User | null): void {
  currentUser = user;
  try {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Non-fatal: store still works in-memory if localStorage is unavailable.
  }
  emit();
}

export async function login(email: string, password: string): Promise<void> {
  const { user } = await api.login(email, password);
  setUser(user);
}

export async function signup(name: string, email: string, password: string): Promise<void> {
  // Signup does not set the session cookie (per the API contract), so log in
  // immediately after to establish the session.
  await api.signup(name, email, password);
  await login(email, password);
}

export async function logout(): Promise<void> {
  try {
    await api.logout();
  } finally {
    setUser(null);
  }
}

/** Clear local auth state without an API call (e.g. after an unexpected 401). */
export function clearAuth(): void {
  setUser(null);
}

export function useAuth(): User | null {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => currentUser,
    () => currentUser,
  );
}
