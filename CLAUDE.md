# CLAUDE.md - OptimalClimbing

This is the **technical map** of OptimalClimbing: stack, schema, endpoints, file layout, and
coding conventions. It answers "where does this go and how is it wired?"

Companion files (read all before starting):
- `PRD.md` - what to build and why (product spec, acceptance criteria).
- `PIPELINE.md` - how the analysis core works (pose, center of mass, move classification, scoring).
- `AGENTS.md` - how to behave while building (workflow, guardrails, definition of done).

You have no memory across context resets. These files are the source of truth. If code and
these docs disagree, treat it as a bug and reconcile them - do not silently follow the code.

---

## Quick Facts (orient here first)

- **What it is:** a web app that analyzes a video of a rock climb and gives per-move,
  technique-focused feedback, centered on the climber's center of mass relative to the holds.
- **Why it exists:** portfolio project for SWE internship applications. Code must be clean and
  defensible in an interview.
- **Build order:** Analysis core first (Phase 1) → Product shell (Phase 2) → Deploy + test
  (Phase 3). Social/gym-map is later and NOT part of V1. Do not build product UI against a
  pipeline that has not been proven on real footage.
- **The core lens:** center of mass proximity to the target hold, per move, excluding dynamic
  moves. The full method is in `PIPELINE.md`.
- **The one hard product invariant:** the app gives per-move feedback, never a single opaque
  score as the whole product. See `PRD.md` → Product Principles.

---

## Settled Decisions

These are decided. A future reset of you will see a simpler-looking alternative and be
tempted to switch. Do not. Changing any of these is a guardrail item - ask first (`AGENTS.md`).
Each line says what was chosen AND what was rejected, so the temptation is pre-answered.

- **Center of mass = segmental, mass-weighted.** Computed from body-segment centroids using
  anthropometric coefficients. NOT the hip-midpoint shortcut. The hip midpoint is wrong
  exactly when arms are overhead, which is most of climbing. Method in `PIPELINE.md`.
- **Holds = user-annotated in V1.** The user taps holds in intended sequence. NOT
  auto-detected. Auto-detection is a separate hard ML project and is deferred (see below).
- **Pose estimation = in-browser (MediaPipe Tasks / TensorFlow.js).** NOT server-side in V1.
  Keeps raw video on the device; only extracted landmarks + hold coordinates are sent on.
- **Move classification = velocity/acceleration threshold on the CoG trajectory.** NOT a
  trained classifier in V1. A trained model is a later upgrade once labeled examples exist.
- **Feedback prose = generated from numeric metrics by a separate layer.** The language layer
  NEVER sees raw video, only computed numbers. Vision produces numbers; language interprets.
- **Depth axis = not scored in V1.** 2D pose cannot measure hips-off-wall reliably. The app
  says so rather than shipping a confident wrong number.

---

## Deferred - Do Not Build

These are real and some are intended eventually, but they are NOT V1 and must not be started
without asking (`AGENTS.md` guardrails). The "why" here is authoritative.

- **Automatic hold detection.** A full object-detection ML project (varied hold shapes,
  colors, lighting, busy walls) needing a large labeled dataset. Kept off the critical path
  on purpose. User annotation replaces it in V1.
- **Depth-based scoring (hips off the wall).** The depth axis is where 2D pose is weakest, and
  it is exactly the axis this cue lives on. Not scored until the method can support it.
- **Social layer / gym map / soft-hard grade ratings.** No CV risk, no dependency on the core,
  so it is sequenced after the core is validated. It has no schema or files yet - do not
  scaffold it. It gets its own PRD section and tables in a future change.
- **"Was this dyno necessary" judgment.** Hard to get right; excluded to avoid confident wrong
  calls. V1 classifies dynamic vs static and scores dynamic moves on landing control only.
- **Native mobile app.** Web-first. Revisit only if browser capture becomes a real bottleneck.

---

## Tech Stack

| Layer            | Technology                                              |
|------------------|---------------------------------------------------------|
| Frontend         | React, Vite, TypeScript, React Router                   |
| Pose estimation  | MediaPipe Tasks (Pose Landmarker) in-browser, WASM      |
| Analysis compute | TypeScript in-browser for CoG + classification (see note)|
| Backend          | Python 3.12+, FastAPI, uvicorn                          |
| DB access        | SQLAlchemy Core (not the ORM) or raw SQL via psycopg    |
| Database         | PostgreSQL 15 + PostGIS extension                       |
| Feedback layer   | Anthropic API call over structured metrics (no video)  |
| Auth             | Custom session + JWT, bcrypt password hashing           |
| Hosting          | Backend on Railway; static frontend on Railway/CDN      |

Note on where analysis runs: pose extraction and the CoG/classification math run client-side
in TypeScript, since the landmarks are already in the browser and this avoids shipping video.
The backend stores the extracted results and runs the feedback-layer call. If a future stage
needs heavier server-side compute, that is a schema/endpoint change - ask first. PostGIS is
included now because the deferred gym-map needs geospatial queries and choosing it up front
avoids a later migration; it is unused in V1.

---

## Directory Structure

```
optimalclimbing/
├── AGENTS.md                ← how the agent should behave
├── CLAUDE.md                ← this file: technical map
├── PRD.md                   ← product requirements
├── PIPELINE.md              ← the analysis core: method + math
├── backend/
│   ├── main.py              ← FastAPI app; router include; startup
│   ├── routers/
│   │   ├── auth.py          ← POST /auth/signup, POST /auth/login, POST /auth/logout
│   │   ├── climbs.py        ← POST /climbs, GET /climbs, GET /climbs/{id}, DELETE /climbs/{id}
│   │   ├── holds.py         ← PUT /climbs/{id}/holds  (replace the annotated hold set)
│   │   └── analyses.py      ← POST /climbs/{id}/analyze, GET /climbs/{id}/analysis
│   ├── core/
│   │   ├── db.py            ← connection pool; get_conn dependency
│   │   ├── security.py      ← bcrypt hash/verify, JWT sign/verify, auth dependency
│   │   └── config.py        ← loads .env; no secrets in source
│   ├── models/
│   │   └── schemas.py       ← Pydantic request/response models
│   ├── feedback/
│   │   └── generate.py      ← turns numeric metrics into prose via the Anthropic API
│   ├── pyproject.toml       ← project + deps
│   └── .env                 ← never commit this file
├── frontend/
│   ├── src/
│   │   ├── main.tsx         ← app entry; router
│   │   ├── routes/
│   │   │   ├── login.tsx
│   │   │   ├── signup.tsx
│   │   │   ├── home.tsx            ← past climbs + upload entry
│   │   │   ├── upload.tsx          ← select video; run in-browser pose extraction
│   │   │   ├── annotate.tsx        ← tap holds in sequence on a still frame
│   │   │   ├── analysis.tsx        ← per-move feedback view
│   │   │   └── profile.tsx
│   │   ├── pipeline/               ← client-side analysis (mirrors PIPELINE.md)
│   │   │   ├── pose.ts             ← MediaPipe landmark extraction from a video
│   │   │   ├── cog.ts              ← segmental center-of-mass calculation
│   │   │   ├── smoothing.ts        ← trajectory filter
│   │   │   ├── moves.ts            ← static vs dynamic classification + per-move metrics
│   │   │   └── types.ts            ← Landmark, CoGPoint, Move, etc.
│   │   ├── services/
│   │   │   └── api.ts       ← ALL API calls live here. Never call fetch() in a component.
│   │   ├── store/
│   │   │   └── auth.ts      ← auth state: current user, login(), logout()
│   │   └── components/      ← shared UI: ClimbCard, MoveBreakdown, HoldMarker, etc.
│   ├── index.html
│   ├── package.json
│   └── .env                 ← VITE_API_URL only
└── pipeline/
    └── fixtures/            ← sample clips + expected stage outputs (regression guards)
                            ← see PIPELINE.md → Fixtures. Committed. Small.
```

---

## Running Locally

### Backend
```bash
cd backend
cp .env.example .env    # then fill in all values
uv sync                 # or: pip install -e .
uvicorn main:app --reload --port 8080
```

### Frontend
```bash
cd frontend
npm install
npm run dev             # Vite dev server, typically :5173
```

---

## Environment Variables

### backend/.env
```
DATABASE_URL=postgresql://postgres:[password]@[host]:5432/postgres
JWT_SECRET=minimum-32-character-secret-key-here
ANTHROPIC_API_KEY=sk-ant-...
PORT=8080
```

Keep a committed `backend/.env.example` with the same keys and placeholder values so a fresh
clone knows what to fill in. The real `.env` is never committed.

### frontend/.env
```
VITE_API_URL=http://localhost:8080
# In production: VITE_API_URL=https://your-app.railway.app
```

---

## Database Schema

Run this SQL once to create all tables. Do NOT modify column names or types without updating
this file AND every affected router in the same change. A schema change is a guardrail item -
see `AGENTS.md`.

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "postgis";  -- unused in V1; reserved for the deferred gym map

CREATE TABLE users (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT        NOT NULL,
  email         TEXT        UNIQUE NOT NULL,
  password_hash TEXT        NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE climbs (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_ref  TEXT,                       -- optional stored reference; video may stay client-side
  status     TEXT        NOT NULL DEFAULT 'draft',  -- draft | annotated | analyzed
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE holds (
  id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  climb_id       UUID    NOT NULL REFERENCES climbs(id) ON DELETE CASCADE,
  sequence_index INT     NOT NULL,       -- tap order = intended sequence, 0-based
  frame_x        REAL    NOT NULL,       -- normalized 0..1 in frame coordinates
  frame_y        REAL    NOT NULL,
  UNIQUE (climb_id, sequence_index)
);

CREATE TABLE analyses (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  climb_id        UUID        NOT NULL UNIQUE REFERENCES climbs(id) ON DELETE CASCADE,
  overall_summary TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE moves (
  id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_id    UUID    NOT NULL REFERENCES analyses(id) ON DELETE CASCADE,
  move_index     INT     NOT NULL,       -- 0-based, ordered
  target_hold_id UUID    REFERENCES holds(id),
  cog_distance   REAL,                   -- normalized CoG-to-target distance at the reach
  move_type      TEXT    NOT NULL,       -- static | dynamic
  confidence     REAL    NOT NULL,       -- pose confidence for this move, 0..1
  note           TEXT,                   -- per-move feedback prose
  UNIQUE (analysis_id, move_index)
);
```

---

## API Endpoints

All routes except `/auth/*` require a valid session (httpOnly cookie).
All times in request and response bodies are ISO 8601 UTC strings.

```
POST   /auth/signup            { name, email, password }         → 201 { data: { user } }
POST   /auth/login             { email, password }               → 200 { data: { user } }   (sets cookie)
POST   /auth/logout                                              → 204                       (clears cookie)

POST   /climbs                 { }                               → 201 { data: { climb } }   (creates a draft)
GET    /climbs                                                   → 200 { data: { climbs } }  (this user, newest first)
GET    /climbs/{id}                                              → 200 { data: { climb, holds, analysis? } }
DELETE /climbs/{id}                                              → 204

PUT    /climbs/{id}/holds      { holds: [{ sequence_index, frame_x, frame_y }] }
                                                                 → 200 { data: { holds } }   (replaces the set)

POST   /climbs/{id}/analyze    { landmarks, frame_rate }         → 201 { data: { analysis } }
GET    /climbs/{id}/analysis                                     → 200 { data: { analysis, moves } }
```

Ownership and scoping rules the routers must enforce:
- Every `/climbs/*` route - the climb must belong to the authed user. Otherwise 404 (do not
  reveal existence of other users' climbs; 404 not 403 for reads/deletes of others' climbs).
- `PUT /climbs/{id}/holds` - rejects an empty hold list with 400. Replaces the whole set
  atomically (delete existing for that climb, insert new), so sequence stays consistent.
- `POST /climbs/{id}/analyze` - requires at least one hold already annotated, else 400. The
  request carries the client-extracted `landmarks` (per-frame) and `frame_rate`; the server
  runs scoring + feedback and persists `analyses` + `moves`. Idempotent per climb: re-analyzing
  replaces the prior analysis (the `analyses.climb_id` UNIQUE enforces one per climb).
- `landmarks` payload shape and the scoring contract are defined in `PIPELINE.md`. The router
  validates shape and returns 400 on malformed input - never trust the client.

---

## Response Format

Every JSON response uses this envelope - no exceptions.

```json
// Success
{ "data": <payload> }

// Error
{ "error": "<human-readable message>" }
```

HTTP status codes:
- `201` Created - POST that creates a resource
- `200` OK - GET, PUT success
- `204` No Content - DELETE, logout success
- `400` Bad Request - missing/invalid fields, empty holds, malformed landmarks
- `401` Unauthorized - missing or invalid session
- `404` Not Found - resource does not exist OR belongs to another user
- `500` Internal Server Error - unexpected failures (log these, never expose details)

Error messages are human-readable and safe. Never return a stack trace to the client.

---

## Feedback Generation

`backend/feedback/generate.py` turns the numeric per-move metrics into coaching prose.

- Input: the structured `moves` metrics (target hold, cog_distance, move_type, confidence)
  plus route-level aggregates. NEVER the raw video, and NEVER raw landmark arrays - only the
  computed summary numbers.
- Output: a short per-move `note` and an `overall_summary`, grounded strictly in the numbers
  passed in. The prompt instructs the model to describe only what the metrics show and to
  avoid inventing detail the numbers do not support.
- Low-confidence moves (below the threshold in `PIPELINE.md`) are described as low-confidence,
  not given a confident correction.
- This call is the only place the Anthropic API is used in the product. Keep it isolated here.

---

## Python Conventions

- Type-hint everything. Public functions have full signatures.
- Handle errors explicitly. No bare `except:`. No swallowed exceptions. Log unexpected DB/IO
  failures and return a generic 500 - never leak internals.
- NO ORM models. Use SQLAlchemy Core or raw parameterized SQL via psycopg. Always
  parameterize - never string-format user input into SQL.
- Pydantic models for all request/response bodies. Validate input at the boundary.
- The authed user is provided by an auth dependency (`core/security.py`), injected into
  routers via FastAPI `Depends`. Do not re-parse the cookie in each handler.
- bcrypt for password hashing (cost factor 12). JWT carries `user_id` and `exp` (7 days).
- Set the session as an httpOnly, Secure, SameSite cookie. Never return the raw token in a body.

---

## TypeScript / React Conventions

- ALL API calls go through `services/api.ts`. No `fetch()` calls in components or routes.
- The session lives in an httpOnly cookie set by the backend. The frontend never reads or
  stores the token itself - NOT in `localStorage`, NOT in JS-accessible state. Auth state in
  `store/auth.ts` holds the current user object, not the token.
- All times sent to and received from the API are ISO 8601 UTC strings. Display in local time.
- No `any` types. If you do not know the type, define an interface in the relevant module
  (pipeline types live in `pipeline/types.ts`).
- The client-side pipeline modules (`pipeline/*.ts`) mirror the stages in `PIPELINE.md`
  one-to-one. Keep that correspondence - a reset agent uses `PIPELINE.md` to understand them.

---

## NEVER Do These Things

- **NEVER change a Settled Decision** (above) without asking. They look re-decidable from
  inside one file and are not.
- **NEVER build anything under Deferred - Do Not Build** (above) or Out of Scope in `PRD.md`
  without asking. That includes auto-detecting holds and scaffolding the gym map.
- **NEVER query PostgreSQL from the frontend.** All DB access goes through the FastAPI backend.
- **NEVER hardcode secrets, tokens, or credentials** in source. Use `.env` only.
- **NEVER store the session token in `localStorage`** or anywhere JS can read it. httpOnly cookie only.
- **NEVER pass raw video or raw landmark arrays to the feedback/language layer.** Metrics only.
- **NEVER swallow an error** in Python or TypeScript. Handle it or let it surface intentionally.
- **NEVER add a package without a clear reason.** Check stdlib / already-installed first.
- **NEVER reveal other users' resources.** Another user's climb returns 404, not its contents.

---

## Build Checklist

Track progress here. Update this file as each item is completed (check the box).
After a context reset, read this FIRST to know what is already done. This checklist is your
resumable state - the git history is not something a fresh context can rely on.

**Phase 1 - Analysis core (prove on real footage before building product around it)**

Status note (2026-07-20): validated on a real bouldering clip (`clip-01`, ~18s, 545 frames).
The full client pipeline (pose -> cog -> smoothing -> moves) was run on real landmarks and outputs
hand-verified and saved as regression fixtures (`pipeline/fixtures/`). `pose.ts` was additionally run
in a real browser (system Chrome via Playwright, dev harness in `frontend/src/App.tsx`): 100%
detection, mean CoM confidence 0.850, and browser landmarks match the committed fixture to mean
|Δx|,|Δy| = 0.004,0.003; the skeleton + CoM overlay is visually correct. The one genuine dynamic
move (a foot-cut top-out) was confirmed against the frames and cleanly separated by the acceleration
threshold. Only remaining Phase-1 gap: the feedback layer still needs one live-API run.

- [x] `pipeline/fixtures/` created; at least one real climbing clip added (see `PIPELINE.md`)
      (clip-01 processed; committed as landmark JSON, raw mp4 gitignored - real face / third-party)
- [x] `pose.ts` - MediaPipe extracts per-frame landmarks from a clip
      (run in a real browser on clip-01: 100% detection, in-browser landmarks match the fixture to
      mean |Δx|,|Δy|=0.004,0.003, skeleton+CoM overlay visually correct, no console errors)
- [x] `cog.ts` - segmental center-of-mass calc; mass fractions sum to 1.0 (see `PIPELINE.md`)
      (ran on real landmarks; mass fractions sum to 1.0; CoM physically sane; confidence propagates)
- [x] `smoothing.ts` - trajectory filter; derivatives are usable (not noise)
      (acceleration cleanly separates static reaches (p99≈2.1) from the dynamic move (7.6))
- [x] `moves.ts` - static vs dynamic classification + per-move CoG-to-hold metric
      (5 moves on clip-01; dynamic move verified against frames; MOVE_PARAMS threshold 3.0 justified)
- [x] End-to-end: a real clip + annotated holds produces sensible per-move numbers
- [x] Regression fixtures saved for pose, cog, and moves stages
      (clip-01.landmarks.json is the pose fixture; expected/cog.json, expected/moves.json)
- [ ] `feedback/generate.py` - numbers → prose, grounded, low-confidence handled
      (written; offline smoke test passes; needs one live-API run with a real ANTHROPIC_API_KEY)

**Phase 2 - Product shell**
- [ ] FastAPI scaffold; DB pool; config from .env
- [ ] POST /auth/signup, /auth/login, /auth/logout (httpOnly cookie)
- [ ] Auth dependency + protected routes
- [ ] POST /climbs, GET /climbs, GET /climbs/{id}, DELETE /climbs/{id} (ownership → 404)
- [ ] PUT /climbs/{id}/holds (replace set; reject empty)
- [ ] POST /climbs/{id}/analyze (validate landmarks; persist analysis + moves; idempotent)
- [ ] GET /climbs/{id}/analysis
- [ ] Frontend: api.ts service layer + auth store
- [ ] Signup / Login screens
- [ ] Home (past climbs + upload entry)
- [ ] Upload screen (in-browser pose extraction)
- [ ] Annotate Holds screen (tap in sequence, undo, clear)
- [ ] Analysis screen (per-move breakdown prominent; score secondary)
- [ ] Profile screen (sign out)

**Phase 3 - Deploy + test**
- [ ] Backend deployed to Railway
- [ ] frontend/.env updated with deployed URL
- [ ] Tested end-to-end in a real browser on a real clip
- [ ] Shown to at least 2 real climbers; feedback matches their sense of the climb
