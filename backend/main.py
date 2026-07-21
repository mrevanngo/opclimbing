"""FastAPI application entry point: startup/shutdown, the response-envelope
exception handlers, CORS for the dev frontend, and router registration.

Every response - including framework-raised errors - uses the envelope from
CLAUDE.md: { "data": ... } on success, { "error": "..." } on failure. Internal
errors are logged and return a generic 500 that never leaks details.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import get_settings
from core.db import close_pool, get_pool
from routers import analyses, auth, climbs, holds

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
