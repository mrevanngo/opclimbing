// The single place API calls happen (CLAUDE.md - TypeScript Conventions).
// Components/routes never call fetch() directly. Requests send the httpOnly
// session cookie via credentials:'include'; the frontend never reads the token.

import type { FrameLandmarks, Hold } from '../pipeline/types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8080';

export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string; // ISO 8601 UTC
}

export interface Climb {
  id: string;
  status: 'draft' | 'annotated' | 'analyzed';
  video_ref: string | null;
  created_at: string;
}

export interface ApiHold {
  id: string;
  sequence_index: number;
  frame_x: number;
  frame_y: number;
}

export interface Analysis {
  id: string;
  climb_id: string;
  overall_summary: string | null;
  created_at: string;
}

export interface Move {
  move_index: number;
  target_hold_id: string | null;
  cog_distance: number | null;
  move_type: 'static' | 'dynamic';
  confidence: number;
  note: string | null;
}

export interface ClimbDetail {
  climb: Climb;
  holds: ApiHold[];
  analysis: Analysis | null;
}

/** Error carrying the HTTP status so callers can branch (e.g. 401 -> login). */
export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${BASE_URL}${path}`, {
      ...init,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, 'Network error - is the API running?');
  }

  if (resp.status === 204) return undefined as T;

  let payload: unknown = null;
  try {
    payload = await resp.json();
  } catch {
    payload = null;
  }

  if (!resp.ok) {
    const message =
      payload && typeof payload === 'object' && 'error' in payload
        ? String((payload as { error: unknown }).error)
        : `Request failed (${resp.status})`;
    throw new ApiError(resp.status, message);
  }
  return (payload as { data: T }).data;
}

// --- Auth ---
export function signup(name: string, email: string, password: string): Promise<{ user: User }> {
  return request('/auth/signup', { method: 'POST', body: JSON.stringify({ name, email, password }) });
}
export function login(email: string, password: string): Promise<{ user: User }> {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
}
export function logout(): Promise<void> {
  return request('/auth/logout', { method: 'POST' });
}

// --- Climbs ---
export function createClimb(): Promise<{ climb: Climb }> {
  return request('/climbs', { method: 'POST' });
}
export function listClimbs(): Promise<{ climbs: Climb[] }> {
  return request('/climbs');
}
export function getClimb(id: string): Promise<ClimbDetail> {
  return request(`/climbs/${id}`);
}
export function deleteClimb(id: string): Promise<void> {
  return request(`/climbs/${id}`, { method: 'DELETE' });
}

// --- Holds ---
export function putHolds(
  id: string,
  holds: { sequence_index: number; frame_x: number; frame_y: number }[],
): Promise<{ holds: ApiHold[] }> {
  return request(`/climbs/${id}/holds`, { method: 'PUT', body: JSON.stringify({ holds }) });
}

// --- Analysis ---
export function analyze(
  id: string,
  landmarks: FrameLandmarks[],
  frameRate: number,
): Promise<{ analysis: Analysis }> {
  return request(`/climbs/${id}/analyze`, {
    method: 'POST',
    body: JSON.stringify({ frame_rate: frameRate, landmarks }),
  });
}
export function getAnalysis(id: string): Promise<{ analysis: Analysis; moves: Move[] }> {
  return request(`/climbs/${id}/analysis`);
}

/** Convert annotator holds to the API payload shape (tap order = sequence). */
export function holdsToPayload(holds: Hold[]): { sequence_index: number; frame_x: number; frame_y: number }[] {
  return holds.map((h) => ({ sequence_index: h.sequenceIndex, frame_x: h.frameX, frame_y: h.frameY }));
}
