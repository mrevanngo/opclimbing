# OptimalClimbing - Product Requirements Document

**Status:** Pre-build
**Owner:** Evan Ngo
**Last updated:** July 2026

This document defines **what to build and why**. It is the product source of truth.

Companion files (read all before starting):
- `CLAUDE.md` - the technical map: stack, schema, endpoints, conventions.
- `PIPELINE.md` - how the analysis core works: pose, center of mass, move classification, scoring.
- `AGENTS.md` - how to behave while building: workflow, guardrails, definition of done.

Every feature below has acceptance criteria. A feature is not done until its acceptance
criteria are demonstrably met - see the Definition of Done in `AGENTS.md`.

---

## Problem Statement

Climbers, especially newer ones, struggle to see their own technique. A coach can watch you
climb and point out that your hips drifted off the wall or that you reached from a bad
position, but most climbers do not have a coach watching every attempt. Video helps, but
watching yourself climb is not the same as knowing what was inefficient about it.

OptimalClimbing analyzes a video of a climb and gives specific, technique-focused feedback.
Its core lens is the climber's center of mass: a well-established rule of thumb is that your
center of mass should be positioned close to the hold you are reaching for, so that the reach
is controlled rather than a lunge. The app tracks the center of mass through the climb,
compares it against the holds being used, and surfaces where technique was efficient and
where it was not - while being smart enough not to penalize dynamic moves where a lunge is
the intended, correct beta.

---

## Target Users

**Primary:** Indoor gym climbers, beginner to intermediate, roughly V0-V6, who want to
improve technique and do not have regular access to coaching. They already film their climbs
on their phones - this is now common gym behavior.

**Persona:** A climber two months in can send V3s but feels like they are muscling through
moves. They film an attempt, upload it, and want to know: was that reach as bad as it felt,
and what should I do differently. They do not want a single mysterious score - they want to
understand the specific moment their technique broke down.

---

## Product Principles

These shape every feature decision. When a tradeoff is unclear, resolve it toward these.

1. **Feedback over verdict.** The app explains what happened, per move. A single 0-100 score
   as the whole product is explicitly rejected - climbers will stress-test it instantly and
   lose trust the first time it rates a clean send poorly. A score may exist, but only
   alongside per-move, per-dimension feedback.
2. **Honest about limitations.** V1 analyzes primarily the plane parallel to the camera.
   Depth (how far the hips are from the wall) is a known weak axis with 2D pose and is not a
   scored dimension in V1. The product says what it can and cannot see rather than pretending.
3. **One lens, clearly framed.** Center of mass proximity is a real principle but is not the
   whole of technique. The app presents it as one lens, not a definitive judgment of the climb.

---

## MVP Feature Set

### Feature 1 - Authentication

Users create an account with name, email, and password. The session persists so users stay
logged in across browser restarts.

**User stories:**
- As a new user, I can sign up so I can upload and analyze climbs.
- As a returning user, I can log in so I can see my past analyses.
- As a logged-in user, my session persists across browser restarts without re-logging in.

**Acceptance criteria:**
- Signup requires name, valid email, and password (min 8 characters).
- Passwords are hashed with bcrypt before storage. Plain text is never stored.
- Login issues a session valid for 7 days.
- Incorrect credentials return a clear error message, not a stack trace.
- The session token is stored in an httpOnly cookie, never in `localStorage` (see `CLAUDE.md`).

---

### Feature 2 - Climb Upload and Hold Annotation

The user uploads a video of a single climb, then marks the holds of the route. Hold
annotation is done by the user in V1 - this is a **settled decision**, not a limitation to be
"fixed" by auto-detecting holds (see `CLAUDE.md` → Settled Decisions and Deferred).

**User stories:**
- As a user, I can upload a video of a single climb from my device.
- As a user, I can mark the holds of the route by tapping them on a still frame.
- As a user, I can mark the holds in the order I intend to use them, so the app knows the
  sequence.

**Acceptance criteria:**
- Accepts common phone video formats (mp4, mov). Rejects files over the size/length limit in
  `CLAUDE.md` with a clear message.
- Pose estimation runs in the browser; the raw video is not required to leave the device for
  analysis (see `CLAUDE.md` → Settled Decisions for why, and what does get uploaded).
- The user taps holds on a chosen still frame. Each tap records a hold position in frame
  coordinates. Holds are recorded in tap order = intended sequence.
- The user can undo the last hold and clear all holds before submitting.
- A climb cannot be submitted for analysis with zero holds annotated - clear error.

---

### Feature 3 - Technique Analysis

The core feature. Given the pose landmarks and the annotated holds, the app computes the
center of mass trajectory, classifies each move as static or dynamic, and scores technique
per move. The full method lives in `PIPELINE.md` - this feature is the product-level contract
for what the user gets.

**User stories:**
- As a user, I get a per-move breakdown of my climb, not just one overall number.
- As a user, for each move I can see whether my center of mass was well-positioned for the
  reach, or too far from the target hold.
- As a user, dynamic moves (lunges, dynos) are recognized as such and not penalized for the
  center of mass being far from the target mid-move.
- As a user, I get plain-language feedback I can act on, not just raw numbers.

**Acceptance criteria:**
- Analysis produces, per move: the target hold, the center of mass distance to that hold at
  the moment of the reach, a classification of static vs dynamic, and a per-move technique note.
- Dynamic moves are identified by the method in `PIPELINE.md` and scored on their own terms
  (e.g. landing control), never penalized for mid-move center of mass distance.
- Plain-language feedback is generated from the numeric analysis by the feedback layer
  (see `CLAUDE.md` → Feedback Generation). The language layer never sees raw video, only the
  computed metrics.
- The result view shows per-move feedback prominently. Any overall score is secondary to the
  per-move breakdown (see Product Principles).
- If pose confidence is too low to analyze a move reliably, that move is flagged as
  low-confidence rather than given a confident wrong answer.

---

### Feature 4 - Analysis History

Users can see their past analyzed climbs and revisit the feedback.

**User stories:**
- As a user, I can see a list of my past analyzed climbs.
- As a user, I can open a past climb and see its full per-move feedback again.

**Acceptance criteria:**
- History lists the user's climbs, most recent first, with date and overall summary.
- Opening a past climb shows the same per-move breakdown produced at analysis time.
- A user can only see their own climbs (403 otherwise).
- A user can delete their own climb and its analysis.

---

## Non-Functional Requirements

- Pose estimation runs client-side; a typical single-climb clip analyzes without a server
  round-trip for the video itself.
- API response time under 500ms for standard (non-analysis) endpoints.
- Works on current Chrome, Safari, and Firefox, desktop and mobile web.
- All timestamps stored in UTC. Displayed in local time in the UI.
- Sessions expire after 7 days.
- The `.env` files are never committed. Secrets live only in environment variables.

---

## Out of Scope - V1

These are explicitly not being built. Do not let scope creep pull these in. Building any of
these without asking the owner is a defect - see Guardrails in `AGENTS.md`. The technical
reasons several of these are deferred are in `CLAUDE.md` → Deferred - Do Not Build; that
section is authoritative on the "why."

| Feature | Reason deferred |
|---|---|
| Automatic hold detection | A separate, harder ML project. User annotation is the settled V1 path. Do not auto-detect. |
| Depth-based scoring (hips off wall) | 2D pose cannot measure the depth axis reliably. Not scored in V1. |
| Social / gym map | Real feature, but zero CV risk and no dependency on the core. Comes after the analysis core is validated. |
| Soft/hard gym grade ratings | Part of the social layer. Deferred with it. |
| "Was this dyno necessary" judgment | Genuinely hard to judge correctly. Out of V1 to avoid confident wrong calls. |
| Native mobile app | Web-first. Native only revisited if browser camera/capture becomes a real bottleneck. |
| Multi-climb / whole-session video splitting | V1 analyzes one climb per upload. |
| Coaching from angles other than camera-parallel | V1 assumes a roughly face-on film. Multi-angle fusion is later. |

The social/gym-map layer is a real intended direction for the product, but it is deliberately
**not** part of the V1 build and has no files of its own yet. Do not scaffold it. When the
analysis core is validated, it gets its own PRD section and schema in a future change.

---

## Data Model Summary

| Table     | Key columns                                                        |
|-----------|--------------------------------------------------------------------|
| users     | id, name, email, password_hash, created_at                        |
| climbs    | id, user_id, video_ref, status, created_at                        |
| holds     | id, climb_id, sequence_index, frame_x, frame_y                    |
| analyses  | id, climb_id, overall_summary, created_at                         |
| moves     | id, analysis_id, move_index, target_hold_id, cog_distance, move_type, confidence, note |

Full SQL schema in `CLAUDE.md`.

---

## Screen Inventory

| Screen         | Route              | Purpose                                                    |
|----------------|--------------------|------------------------------------------------------------|
| Login          | /login             | Email + password login                                     |
| Signup         | /signup            | Create account                                             |
| Home           | /                  | List of past climbs + upload entry point                   |
| Upload         | /upload            | Select video, run in-browser pose extraction               |
| Annotate Holds | /climb/[id]/holds  | Tap holds in sequence on a still frame                     |
| Analysis       | /climb/[id]        | Per-move technique breakdown and feedback                  |
| Profile        | /profile           | Account info, sign out                                     |

---

## Build Phases

### Phase 1 - Analysis core (build this first, before any accounts or UI polish)
The riskiest and most valuable part. Prove the pipeline on real climbing footage before
building product scaffolding around it. See `PIPELINE.md` for the method and `CLAUDE.md`
Build Checklist for the ordered items. If the core does not produce sensible feedback on real
clips, nothing else matters, so it goes first.

### Phase 2 - Product shell
Auth, upload flow, hold annotation UI, analysis result view, history. Wraps the validated
core in a usable product.

### Phase 3 - Deploy and test with real climbers
Deploy, then put it in front of actual climbers and check whether the feedback matches their
own sense of how the climb went. Fix what real use surfaces.

### (Later, not V1) Phase 4 - Social / gym map
Only after the core is validated. Gets its own PRD section and schema then. Not now.

---

## Portfolio Talking Points

These are the decisions worth articulating in a SWE interview.

**1. Segmental center of mass, not the hip shortcut**
The center of mass is computed as a mass-weighted average of body segment centroids using
standard anthropometric coefficients, not approximated by the hip midpoint. This is more
accurate exactly when it matters - arms overhead, which is most of climbing - and is a
defensible biomechanics choice rather than a convenient hack. See `PIPELINE.md`.

**2. User-annotated holds instead of auto-detection**
V1 has the user tap the holds rather than training a hold detector. This removes the single
riskiest ML dependency from the critical path, lets the entire scoring pipeline be built and
validated independently, and sidesteps route-sequencing ambiguity by capturing tap order as
intended sequence. Auto-detection is a later "magic" feature, not a V1 blocker.

**3. Vision produces numbers, language interprets them**
The scoring layer emits structured metrics; a separate feedback layer turns those into
coaching prose and never touches raw video. This separation keeps the language grounded,
lets scoring be tuned without touching presentation, and is cheap to run.

**4. Honest scoping of the depth axis**
2D pose cannot reliably measure how far the hips are from the wall, so V1 does not score that
dimension and says so, rather than shipping a confident measurement that is wrong. Knowing
the boundary of what a method can support is itself the engineering point.

**5. Client-side pose estimation**
Pose runs in the browser, so the raw video need not leave the device for analysis. This is a
privacy win, removes per-video server GPU cost, and tolerates gym wifi. Only small extracted
data (landmarks, hold coordinates) is sent on for storage.
