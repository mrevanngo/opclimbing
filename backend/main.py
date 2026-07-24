"""FastAPI application entry point: startup/shutdown, the response-envelope
exception handlers, CORS for the dev frontend, and router registration.

Every response - including framework-raised errors - uses the envelope from
CLAUDE.md: { "data": ... } on success, { "error": "..." } on failure. Internal
errors are logged and return a generic 500 that never leaks details.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import get_settings
from core.db import apply_schema, close_pool, get_pool
from routers import analyses, auth, climbs, holds, stats

logger = logging.getLogger("optimalclimbing")

# Dev frontend origins (Vite). Credentials are allowed so the session cookie
# flows; with credentials the origin list must be explicit (never "*").
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    get_settings()  # fail fast on missing config
    get_pool()  # open the connection pool
    # Initialize a fresh deployment DB (Railway) on boot. Idempotent; opt-in so
    # local dev, which applies schema.sql manually, is unaffected.
    if os.environ.get("RUN_MIGRATIONS", "").lower() in ("1", "true", "yes"):
        logger.info("RUN_MIGRATIONS set - applying schema")
        apply_schema()
    yield
    close_pool()


app = FastAPI(title="OptimalClimbing API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    # 204 carries no body.
    if exc.status_code == status.HTTP_204_NO_CONTENT:
        return JSONResponse(content=None, status_code=204)
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    # Malformed/missing fields -> 400 with a safe, human-readable message.
    first = exc.errors()[0] if exc.errors() else None
    if first is not None:
        loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
        msg = first.get("msg", "Invalid request")
        detail = f"{loc}: {msg}" if loc else msg
    else:
        detail = "Invalid request"
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"error": detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error"},
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {"data": {"status": "ok"}}


app.include_router(auth.router)
app.include_router(climbs.router)
app.include_router(holds.router)
app.include_router(analyses.router)
app.include_router(stats.router)


# --- Serve the built frontend from the same origin (production/Railway) --------
# When FRONTEND_DIST points at a Vite build, the API and the app share one origin,
# so the session cookie stays first-party and there is no CORS. Registered AFTER
# the routers so /auth, /climbs, /stats, /health always win; everything else
# falls back to index.html for client-side routing. In local dev FRONTEND_DIST is
# unset and Vite serves the frontend separately.
_dist = os.environ.get("FRONTEND_DIST")
if _dist and Path(_dist).is_dir():
    _dist_path = Path(_dist)
    _assets = _dist_path / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        # Serve a real static file if it exists (favicon, icons), else the SPA shell.
        candidate = _dist_path / full_path
        if full_path and candidate.is_file() and candidate.is_relative_to(_dist_path):
            return FileResponse(candidate)
        return FileResponse(_dist_path / "index.html")
