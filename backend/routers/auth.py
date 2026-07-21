"""Authentication routes: signup, login, logout.

Contract (CLAUDE.md - API Endpoints):
  POST /auth/signup  { name, email, password } -> 201 { data: { user } }
  POST /auth/login   { email, password }        -> 200 { data: { user } }  (sets cookie)
  POST /auth/logout                             -> 204                       (clears cookie)

Signup does not set the session cookie (login does) - it matches the documented
contract, and the frontend logs in immediately after a successful signup.
"""

from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Response, status

from core.db import get_conn
from core.envelope import ok
from core.security import (
    create_session_token,
    hash_password,
    set_session_cookie,
    clear_session_cookie,
    verify_password,
)
from models.schemas import LoginRequest, SignupRequest, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(
    body: SignupRequest,
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    password_hash = hash_password(body.password)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (name, email, password_hash)
                VALUES (%s, %s, %s)
                RETURNING id, name, email, created_at
                """,
                (body.name, str(body.email), password_hash),
            )
            row = cur.fetchone()
    except psycopg.errors.UniqueViolation as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        ) from exc
    assert row is not None  # RETURNING on a successful INSERT
    return ok({"user": UserResponse(**row).model_dump(mode="json")})


@router.post("/login")
def login(
    body: LoginRequest,
    response: Response,
    conn: psycopg.Connection[dict[str, Any]] = Depends(get_conn),
) -> dict[str, Any]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, email, password_hash, created_at FROM users WHERE email = %s",
            (str(body.email),),
        )
        row = cur.fetchone()
    # Same 401 whether the email is unknown or the password is wrong - do not
    # reveal which accounts exist.
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password"
        )
    token = create_session_token(row["id"])
    set_session_cookie(response, token)
    user = {k: row[k] for k in ("id", "name", "email", "created_at")}
    return ok({"user": UserResponse(**user).model_dump(mode="json")})


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> Response:
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
