-- OptimalClimbing database schema. Source of truth is CLAUDE.md -> Database Schema;
-- this file must stay identical to it. Apply once to a fresh database.
-- A schema change is a guardrail item (see AGENTS.md): update CLAUDE.md AND every
-- affected router in the same change.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "postgis";  -- unused in V1; reserved for the deferred gym map

CREATE TABLE IF NOT EXISTS users (
  id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT        NOT NULL,
  email         TEXT        UNIQUE NOT NULL,
  password_hash TEXT        NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- A climb is one logbook entry. Video analysis is OPTIONAL extra data on it:
-- most logged climbs have no video, and the log fields drive the progression
-- analytics (see the stats endpoints).
CREATE TABLE IF NOT EXISTS climbs (
  id         UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_ref  TEXT,                       -- optional stored reference; video may stay client-side
  status     TEXT        NOT NULL DEFAULT 'draft',  -- draft | annotated | analyzed
  created_at TIMESTAMPTZ DEFAULT NOW(),
  -- Logbook fields (all nullable: a video-only draft has none of them yet).
  grade      INT         CHECK (grade BETWEEN 0 AND 17),      -- V-scale
  angle      TEXT        CHECK (angle IN ('slab','vertical','overhang','roof')),
  outcome    TEXT        CHECK (outcome IN ('flash','send','attempt')),
  attempts   INT         NOT NULL DEFAULT 1 CHECK (attempts >= 1),
  beta_notes TEXT,
  climbed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- when it was climbed (backfillable)
);

-- Hold types present on a climb. Many-to-many so send rate can be aggregated
-- per hold type ("which hold types do I fail on").
CREATE TABLE IF NOT EXISTS climb_hold_types (
  climb_id  UUID NOT NULL REFERENCES climbs(id) ON DELETE CASCADE,
  hold_type TEXT NOT NULL CHECK (hold_type IN ('crimp','jug','sloper','pinch','pocket')),
  PRIMARY KEY (climb_id, hold_type)
);

CREATE INDEX IF NOT EXISTS climbs_user_climbed_at_idx ON climbs (user_id, climbed_at DESC);

CREATE TABLE IF NOT EXISTS holds (
  id             UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
  climb_id       UUID    NOT NULL REFERENCES climbs(id) ON DELETE CASCADE,
  sequence_index INT     NOT NULL,       -- tap order = intended sequence, 0-based
  frame_x        REAL    NOT NULL,       -- normalized 0..1 in frame coordinates
  frame_y        REAL    NOT NULL,
  UNIQUE (climb_id, sequence_index)
);

CREATE TABLE IF NOT EXISTS analyses (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  climb_id        UUID        NOT NULL UNIQUE REFERENCES climbs(id) ON DELETE CASCADE,
  overall_summary TEXT,
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS moves (
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
