# Pipeline Fixtures - Regression Guard

This directory holds the lightweight regression guard described in `PIPELINE.md` → Fixtures.
One real climbing clip's extracted landmarks and one confirmed expected output per numbers-heavy stage (cog, moves).
Do NOT grow this into a heavy golden-file harness - one clip and output per stage is the bar.

## Status: populated (clip-01)

A real bouldering clip (`clip-01`, ~18s, 545 frames, 30fps, phone-filmed roughly wall-parallel) was
processed on 2026-07-20. The raw `clip-01.mp4` is intentionally **not committed** - it shows a real
face and is a third-party social clip (see `.gitignore` and AGENTS.md). Per `PIPELINE.md` → Fixtures,
the committed input is the extracted landmark JSON instead.

Landmarks were extracted with the **same model `pose.ts` loads** (`pose_landmarker_full.task`,
MediaPipe Pose Landmarker) - 100% detection across all 545 frames, per-frame CoM confidence
0.71-0.98. The cog / smoothing / moves outputs below were produced by running the actual
`frontend/src/pipeline/*.ts` stage code on these committed landmarks.

## Files

```
pipeline/fixtures/
├── clip-01.landmarks.json   INPUT: per-frame 33 landmarks {x,y,z,visibility} + frameRate.
│                            Committed stand-in for the raw clip (rounded for size/stability).
├── clip-01.holds.json       INPUT: 6 holds in ascending tap order, normalized frame coords.
│                            Annotated from the climber's planted-hand positions (V1 tap flow).
├── expected/
│   ├── cog.json             Stage 2 output: segmental CoM point per frame (from cog.ts).
│   └── moves.json           Stage 4 output: per-move metrics + the MOVE_PARAMS used (from moves.ts).
└── README.md
```

(No separate `expected/pose.json`: `clip-01.landmarks.json` *is* the pose-stage output, committed as
the input the other stages consume.)

## Confirmed correctness (blessing the numbers)

- **cog:** mass fractions sum to 1.0 (cog.ts throws at import otherwise); CoM sits in a physically
  sane spot on the climber's trunk; low per-landmark visibility propagates into frame confidence.
- **moves:** 5 moves - four static reaches (cog-to-target distance 0.19-0.23) and one dynamic
  top-out. The dynamic move (move 4, t=13.0-17.8s) was verified by hand against the frames: the
  climber cuts the right foot and throws the center of mass upward to the finish hold. Its peak CoM
  acceleration is 7.58 units/s² vs a p99 of 2.1 for the rest of the climb, so the
  `dynamicAccelThreshold = 3.0` cleanly separates it - the threshold is now justified on real
  footage, not guessed.

## How to use (from PIPELINE.md)

1. Re-run a stage on `clip-01.landmarks.json` (+ `clip-01.holds.json` for moves).
2. Compare against the matching `expected/*.json`.
3. A diff means an upstream change moved the numbers - decide whether that was intended.

It is a consistency-and-regression guard, not proof of correctness; the "correct" numbers are only as
good as the reasoning above that blessed them.
