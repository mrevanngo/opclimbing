---
name: pipeline-stage
description: >
  Use when adding or modifying a stage of the OptimalClimbing analysis pipeline - anything in
  frontend/src/pipeline/*.ts (pose, cog, smoothing, moves) or the scoring aggregation. Covers
  the standard shape every stage follows: read the method from PIPELINE.md, respect the settled
  method, propagate confidence, reason through correctness, and save the regression fixture.
  Trigger whenever a task touches the pipeline stages or asks to build the analysis core from
  PIPELINE.md. Do NOT use for ordinary API endpoints - use the go-style endpoint pattern in
  CLAUDE.md for those.
---

# Pipeline Stage Skill - OptimalClimbing

Every analysis stage follows the same shape. Building them from memory causes drift, and
because a context reset erases the memory that a stage's numbers were ever correct, drift here
is silent and dangerous. Follow this procedure so every stage stays consistent and defensible.

Read `PIPELINE.md` for the stage's exact method (math, inputs, outputs) before writing.
Read `AGENTS.md` for the Definition of Done for pipeline tasks. This skill is the how, not the what.

## The stage shape

1. **Read the method first.** Open `PIPELINE.md` and find the stage. The math there is a
   Settled Decision. Do not substitute a "simpler" method (e.g. hip-midpoint CoM instead of
   segmental) - that is a guardrail item, ask first. If `PIPELINE.md` and the code disagree,
   that is a bug to reconcile, not a choice to make silently.
2. **Match the input/output contract.** Each stage's output is the next stage's input, and the
   shapes are named in `PIPELINE.md`. Keep types in `pipeline/types.ts`. No `any`.
3. **Consume real time where relevant.** Velocity/acceleration need the frame rate. Do not
   assume frames are evenly spaced without checking; carry the frame rate through.
4. **Propagate confidence, never hide it.** If input landmarks are low-visibility, the output
   is lower-confidence. Mark it and pass it on. A confident answer built on garbage landmarks
   is worse than an honest low-confidence flag.
5. **Respect the depth exclusion.** `z` is unreliable. Do not build scored logic on depth
   (Settled Decision). Use `x, y`.
6. **Reason through correctness out loud.** Before calling it done, write why it is right:
   for CoM, that mass fractions sum to ~1.0 and the weighted average is correct; for moves,
   that the frame classified dynamic is actually the dynamic one. This reasoning is required
   by Definition of Done and is what a reset version of you cannot reconstruct later.
7. **Save the regression fixture.** Run the stage on a real clip from `pipeline/fixtures/`,
   confirm the output, and save it as the stage's expected JSON (see `PIPELINE.md` → Fixtures).
   One clip is enough. This is how a future session detects a silent numeric regression.

## Stage-specific notes (from PIPELINE.md)

- **pose.ts** - 33 MediaPipe landmarks per frame with visibility; record frame rate; verify
  landmark indices against the current library version, not memory.
- **cog.ts** - segmental mass-weighted CoM; the mass-fractions-sum-to-1.0 check is your
  cheapest correctness signal, run it every time.
- **smoothing.ts** - filter position, then differentiate; if acceleration is dominated by
  jitter the filter is under-tuned - fix before trusting move classification.
- **moves.ts** - threshold-based static/dynamic; static scored on CoG-to-target distance at
  the reach, dynamic scored on landing control only, never on mid-move distance. No "was the
  dyno necessary" (deferred).

## Verify before claiming done

- The stage runs end-to-end on a real fixture clip, not just a synthetic input.
- Your written correctness reasoning is in the summary.
- The regression fixture (input + confirmed expected output) is saved under
  `pipeline/fixtures/`.
- The matching item in the Build Checklist in `CLAUDE.md` is checked off.

Do not grow the fixtures into a heavy golden-file harness - one clip and output per stage is
the bar. It is a regression guard, not proof of correctness.
