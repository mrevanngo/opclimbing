# PIPELINE.md - OptimalClimbing Analysis Core

This file defines **how the analysis works**: the CV and scoring method, stage by stage, with
the math a reset version of you needs to rebuild any stage correctly.

Companion files:
- `PRD.md` - what the analysis must deliver to the user (Feature 3).
- `CLAUDE.md` - where the code lives (`frontend/src/pipeline/*`, `backend/feedback/`), the
  Settled Decisions, and the API contract for `POST /climbs/{id}/analyze`.
- `AGENTS.md` - the Definition of Done for pipeline tasks (including the fixtures guard).

The pipeline is the riskiest, highest-value part of the product and is built FIRST. If it
does not produce sensible feedback on real climbing footage, no amount of product polish
matters. Everything here is a Settled Decision - changing a method is a guardrail item
(ask first), because each choice looks re-decidable from inside this file and is not.

The stages, in order:
`pose → center of mass → smoothing → move classification → per-move scoring → feedback prose`
The first five run client-side (`frontend/src/pipeline/*`). Feedback runs server-side
(`backend/feedback/generate.py`). The API boundary between them is in `CLAUDE.md`.

---

## Why correctness here needs a regression guard (read once)

For ordinary backend code, "it runs and returns the right status" proves it works. Pipeline
correctness is different: the code can run cleanly and still be wrong, because the truth is in
numbers over time (landmark positions, a CoG trajectory, a velocity curve) that the running
code cannot self-evidently confirm. You can reason about correctness while you build a stage -
and you should, and that reasoning is part of Definition of Done. But a later context reset of
you cannot re-derive those numbers by reading code, so it cannot notice if an upstream change
silently moved them.

That is the entire reason for fixtures (last section). They are not a heavyweight test regime.
They are one saved clip and its output per numbers-heavy stage, so a future session can tell
whether the numbers still hold. Build them as a lightweight habit when you reach each stage,
not as upfront scaffolding.

---

## Stage 1 - Pose estimation (`pipeline/pose.ts`)

Use MediaPipe Tasks Pose Landmarker in the browser (WASM). For each video frame, it yields
33 landmarks with normalized `x, y` in `[0,1]`, a rough `z` (depth relative to hips), and a
per-landmark `visibility`/presence score.

- Input: a video element / frames + the frame rate.
- Output: an array of frames, each an array of 33 landmarks `{x, y, z, visibility}`.
- Record the frame rate - later stages need real time to compute velocity.
- **The `z` axis is unreliable.** Do not build scored logic on depth (Settled Decision:
  depth is not scored in V1). Use `x, y` for scoring.
- Track a per-frame confidence (e.g. mean visibility of the landmarks that matter for CoG). A
  move built from low-visibility frames is flagged low-confidence downstream, not scored
  confidently.

Landmark indices you will need (MediaPipe Pose): shoulders 11/12, elbows 13/14, wrists 15/16,
hips 23/24, knees 25/26, ankles 27/28. Verify against the current MediaPipe docs when building -
do not trust this list from memory if the library version differs.

---

## Stage 2 - Center of mass (`pipeline/cog.ts`)

**Settled Decision: segmental, mass-weighted center of mass. NOT the hip midpoint.** The hip
midpoint is wrong exactly when the arms are raised, which is most of climbing, so it would
corrupt the core metric. This is textbook biomechanics and is defensible in an interview.

Method: the body is a set of segments. Each segment has (a) a fraction of total body mass and
(b) a center-of-mass location expressed as a fraction of the distance from its proximal to its
distal joint. Compute each segment's CoM point in frame coordinates, multiply by its mass
fraction, sum, and divide by the total mass fraction (which is 1.0 if the set is complete).

Standard anthropometric values (Dempster, widely used). Mass fractions are per segment; for
paired limbs the fraction below is PER SIDE (left and right each contribute).

| Segment            | Mass fraction | CoM location (proximal → distal) | Endpoints (proximal, distal)     |
|--------------------|---------------|----------------------------------|----------------------------------|
| Head + neck        | 0.081         | -                                | approximate at shoulder midpoint |
| Trunk              | 0.497         | -                                | shoulder midpoint → hip midpoint |
| Upper arm (each)   | 0.028         | 0.436 from proximal              | shoulder → elbow                 |
| Forearm (each)     | 0.016         | 0.430 from proximal              | elbow → wrist                    |
| Hand (each)        | 0.006         | 0.494 from proximal              | wrist → (approx at wrist)        |
| Thigh (each)       | 0.100         | 0.433 from proximal              | hip → knee                       |
| Shank (each)       | 0.0465        | 0.433 from proximal              | knee → ankle                     |
| Foot (each)        | 0.0145        | 0.5 (approx)                     | ankle → (approx at ankle)        |

- For a paired segment, compute BOTH sides and weight each by its own fraction.
- For the trunk, use the shoulder midpoint and hip midpoint as the two endpoints, CoM near
  the midpoint region; the trunk dominates so get it right.
- **Sanity check that mass fractions sum to ~1.0** across all segments and sides. If your set
  does not sum near 1.0 you have a missing or double-counted segment. This is the cheapest
  correctness check you have - do it every time you touch this file. Head/neck as a point at
  the shoulder midpoint is an approximation; the sum check still holds.
- A segment endpoint below the visibility threshold makes that frame's CoM lower-confidence;
  propagate that, do not silently use a garbage landmark.

Output: one CoM point `{x, y}` in normalized frame coordinates per frame.

---

## Stage 3 - Smoothing (`pipeline/smoothing.ts`)

Frame-to-frame landmarks jitter, and CoM inherits that jitter. Move classification depends on
velocity and acceleration - derivatives - which amplify noise badly. Smooth the CoM trajectory
before differentiating.

- Apply a filter to the CoM `{x, y}` series over time. A one-euro filter is a good default
  (low latency, tunable). A Kalman filter is also acceptable. Do not over-engineer.
- Smooth position, then derive velocity and acceleration from the smoothed series.
- The goal is a velocity/acceleration signal where a real dynamic move is clearly separable
  from smoothing artifacts. If your acceleration curve is dominated by jitter, the filter is
  under-tuned - fix that before trusting Stage 4.

Output: smoothed CoM trajectory plus its velocity and acceleration over time.

---

## Stage 4 - Move classification + per-move metric (`pipeline/moves.ts`)

First, segment the climb into moves. A move is a reach toward the next hold in sequence
(holds come from the user's tap-order annotation - see `CLAUDE.md` schema, `holds.sequence_index`).
The transition into a move is when the climber commits toward the next target hold; a simple,
defensible approach ties each move window to the interval ending when a hand reaches the next
annotated hold position. Keep the segmentation logic explainable.

**Settled Decision: static vs dynamic by a velocity/acceleration threshold. NOT a trained
model in V1.** A trained classifier is a later upgrade once labeled examples exist.

- **Static move:** low, smooth CoM velocity - a deliberate weight shift and controlled reach.
- **Dynamic move:** a sharp CoM acceleration spike, often followed by a near-ballistic phase
  (parabolic CoM path if the hands leave the wall). Threshold on peak acceleration; optionally
  confirm with an airborne phase (limb landmarks not near any annotated hold).

Per-move metric:
- **Static move:** the core metric is CoM-to-target-hold distance at the moment of the reach
  (the frame the reaching hand arrives at / is nearest the target hold), in normalized frame
  units. Smaller = the center of mass was well-positioned under the reach = better technique.
- **Dynamic move:** do NOT score mid-move CoM distance - a lunge REQUIRES the CoM to be far,
  and penalizing that is wrong (this is the "be smart about dynamic moves" requirement in the
  PRD). Score dynamic moves on landing control instead: how settled the CoM is at the moment
  the target hold is caught. Do NOT attempt "was this dyno necessary" - that is deferred.
- Attach the pose confidence for the move's frames. Below the confidence threshold, mark the
  move low-confidence; downstream it is described as such, not given a confident correction.

Output, per move: `{ move_index, target_hold_id, move_type, cog_distance (static) or
landing_control (dynamic), confidence }`. This is exactly the shape persisted to the `moves`
table and passed to feedback (see `CLAUDE.md`).

---

## Stage 5 - Scoring aggregation

Aggregate per-move metrics into what the user sees. Per the PRD Product Principles, the
per-move breakdown is the product; any overall number is secondary.

- Keep per-move results first-class. If you produce an overall score, derive it transparently
  from the per-move metrics (e.g. distribution of static-move CoG distances), and never let it
  stand alone as the whole result.
- Do not collapse everything into one 0-100 as the primary output. Climbers will stress-test a
  single number and lose trust the first time it rates a clean send poorly.

---

## Stage 6 - Feedback prose (`backend/feedback/`)

Runs server-side. Turns the numeric per-move metrics into short coaching notes through a
**pluggable provider** (`FEEDBACK_PROVIDER`): `template` (default, deterministic, no LLM),
`ollama` (local LLM), or `anthropic` (hosted). See `CLAUDE.md` → Feedback Generation.

- Input: the structured metrics only - target hold, cog_distance / landing_control, move_type,
  confidence, and route aggregates. **Never** raw video, **never** raw landmark arrays. This
  separation is settled; the provider behind it is not.
- Output: a per-move `note` and an `overall_summary`, grounded strictly in the numbers. Every
  provider describes only what the metrics show and does not invent detail; the default `template`
  provider derives each sentence directly from a number, so it cannot invent anything.
- Low-confidence moves are described as low-confidence.
- If a provider is an LLM, this is the only place a language model touches the pipeline. Vision
  produced numbers; the feedback layer only interprets them.

---

## The `landmarks` payload (client → server contract)

`POST /climbs/{id}/analyze` carries the client-extracted data. Keep this shape stable; it is
part of the API contract in `CLAUDE.md`.

```
{
  "frame_rate": 30,
  "landmarks": [                      // one entry per analyzed frame
    [            //   33 landmarks per frame
      { "x": 0.51, "y": 0.42, "z": -0.03, "visibility": 0.98 },
      ...
    ],
    ...
  ]
}
```

Holds are already stored server-side (from `PUT /climbs/{id}/holds`), so they are not resent.
The server validates this shape and returns 400 on anything malformed - never trust the client.

Design choice worth an interview note: Stages 2-4 could run client-side (they already do) and
send only the computed per-move metrics, OR the client can send landmarks and the server can
recompute. Sending landmarks keeps the scoring authoritative on the server and lets scoring be
fixed without shipping new client code. Either is defensible; the contract above sends landmarks.
If you change which side computes scoring, that is a Settled-Decision-level change - ask first.

---

## Fixtures - the lightweight regression guard

This is the ONE piece of test infrastructure the pipeline needs, and it is deliberately small.
It exists because context resets destroy the memory that these numbers were ever correct.

`pipeline/fixtures/` holds, per numbers-heavy stage (pose, cog, moves):
- one short real climbing clip (or the extracted landmark JSON for it, if the clip cannot be
  committed for rights/size reasons), and
- that stage's output for that input, saved as JSON (the "expected" numbers).

When you build or change a numbers-heavy stage:
1. Run the stage on the fixture input.
2. Reason through and confirm the output is correct (mass fractions sum to 1.0, CoM sits in a
   sane spot, the dynamic move is the one that is actually dynamic, etc.). Write that reasoning
   in your summary.
3. Save the confirmed output as the fixture's expected JSON.

When you later touch an upstream stage, re-run and compare against the saved expected output.
A diff means you moved the numbers - decide whether that was intended. This is what lets a
fresh context catch a silent regression it otherwise could not, because it never saw the
numbers be right.

Keep it honest about what it is: a consistency-and-regression guard, not proof of correctness.
The "correct" numbers are only as good as the reasoning that blessed them. Do NOT grow this
into a large golden-file harness - one clip and output per stage is the bar (`AGENTS.md`).
