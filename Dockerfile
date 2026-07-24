# Single-image deploy (Railway, "all on Railway"): build the frontend, then run
# the FastAPI backend which serves that build from the same origin. One process,
# one domain -> the session cookie stays first-party and there is no CORS.

# --- Stage 1: build the React/Vite frontend ---------------------------------
FROM node:22-slim AS frontend
WORKDIR /fe
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Empty API base -> relative, same-origin requests (see services/api.ts).
ENV VITE_API_URL=""
RUN npm run build            # -> /fe/dist

# --- Stage 2: Python backend that serves the build --------------------------
FROM python:3.12-slim AS backend
WORKDIR /app
COPY backend/ ./
# Editable install: deps from pyproject, and `core`/`routers`/... resolve to
# /app so schema.sql (read relative to the package) is found at runtime.
RUN pip install --no-cache-dir -e .

# The built frontend, served from the same origin as the API.
COPY --from=frontend /fe/dist ./static
ENV FRONTEND_DIST=/app/static
ENV RUN_MIGRATIONS=1

# Railway injects PORT; bind to it (fallback 8080 for local runs).
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
