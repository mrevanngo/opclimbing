"""Database access: a psycopg 3 connection pool and a FastAPI dependency that
hands out a connection per request.

No ORM (CLAUDE.md - Python Conventions): callers use raw parameterized SQL via
psycopg. Rows come back as dicts (``dict_row``) so routers can build response
payloads without positional indexing.
"""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from core.config import get_settings

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    """Lazily open the shared connection pool. Opened on first use and on
    FastAPI startup (main.py); closed on shutdown."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=get_settings().database_url,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def apply_schema() -> None:
    """Apply schema.sql idempotently (all statements are IF NOT EXISTS). Used to
    initialize a fresh deployment database (e.g. Railway) at startup when
    RUN_MIGRATIONS is set. Safe to run repeatedly; a no-op on an existing schema.
    """
    sql = _SCHEMA_PATH.read_text(encoding="utf-8")
    with get_pool().connection() as conn:
        # No parameters -> psycopg uses the simple protocol, so the whole
        # multi-statement script runs in one call.
        conn.execute(sql)  # type: ignore[arg-type]


def get_conn() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    """FastAPI dependency: yield a pooled connection for one request.

    The connection is returned to the pool when the request ends. psycopg
    commits on a clean exit of the connection's context and rolls back on an
    exception, so a handler that raises does not persist a partial write.
    """
    pool = get_pool()
    with pool.connection() as conn:
        yield conn
