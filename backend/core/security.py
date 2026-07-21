"""Security primitives: bcrypt password hashing, JWT session tokens, and the
FastAPI auth dependency that resolves the current user from the session cookie.

Settled behavior (CLAUDE.md):
- bcrypt cost factor 12.
- JWT carries ``user_id`` and ``exp`` (7 days).
- The session lives in an httpOnly, Secure, SameSite cookie. The raw token is
  never returned in a response body and never read by the frontend.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, Final
from uuid import UUID

import bcrypt
import jwt
import psycopg
from fastapi import Cookie, Depends, HTTPException, Response, status

from core.config import get_settings
from core.db import get_conn

SESSION_COOKIE: Final = "session"
_ALGORITHM: Final = "HS256"
SESSION_TTL: Final = dt.timedelta(days=7)
_BCRYPT_ROUNDS: Final = 12


# --- Passwords -------------------------------------------------------------

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Malformed stored hash - treat as a failed match, never crash the login.
        return False


# --- JWT session tokens ----------------------------------------------------

def create_session_token(user_id: UUID) -> str:
    now = dt.datetime.now(tz=dt.timezone.utc)
    payload = {"user_id": str(user_id), "iat": now, "exp": now + SESSION_TTL}
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=_ALGORITHM)


def _decode_session_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, get_settings().jwt_secret, algorithms=[_ALGORITHM])
        return UUID(payload["user_id"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        ) from exc


def set_session_cookie(response: Response, token: str) -> None:
    """Set the session as an httpOnly, Secure, SameSite=Lax cookie."""
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=int(SESSION_TTL.total_seconds()),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


# --- Auth dependency -------------------------------------------------------

class CurrentUser:
    """The authenticated user, injected into protected routes via Depends."""

    def __init__(self, id: UUID, name: str, email: str) -> None:
        self.id = id
        self.name = name
        self.email = email


def get_current_user(
    session: str | None = Cookie(default=None),
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> CurrentUser:
    """Resolve the current user from the session cookie or raise 401.

    Verifies the JWT, then confirms the user still exists (a token for a
    deleted account must not authenticate).
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    user_id = _decode_session_token(session)
    with conn.cursor() as cur:
        cur.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
        row = cur.fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return CurrentUser(id=row["id"], name=row["name"], email=row["email"])
