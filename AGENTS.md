# AGENTS.md - OptimalClimbing

This file defines **how an AI agent should behave** while working on OptimalClimbing.
It is about conduct and process, not product scope.

- **What to build** → see `PRD.md`
- **How the system is wired** (stack, schema, endpoints, conventions) → see `CLAUDE.md`
- **How the analysis pipeline works** (the CV/scoring core) → see `PIPELINE.md`
- **How to behave while building it** → this file

Read `PRD.md`, `CLAUDE.md`, `PIPELINE.md`, and this file before starting any task.

You are a single continuous agent, but your context does NOT survive forever. It resets when
token limits are hit or a session ends. Every reset, you start from nothing except these
files. Treat that as the normal case, not the exception. These files are your only durable
memory. Trust them over your own assumptions, and when you make a decision that a future
reset of you would need to know, write it into the right file in the same change.

---

## First 60 Seconds of Any Task

1. Read `PRD.md`, `CLAUDE.md`, `PIPELINE.md`, and this file if you have not already this session.
2. Locate the task in the **Build Checklist** in `CLAUDE.md`. Know which phase you are in.
3. Confirm any prerequisite checklist items are actually done before starting a dependent one.
   (Do not build the scoring layer before the CoG pipeline produces a trajectory.)
4. Re-read the **Settled Decisions** and **Deferred - Do Not Build** sections in `CLAUDE.md`.
   These exist specifically because a reset version of you will be tempted to re-decide them.
   Do not re-litigate a settled decision or pull in deferred scope because it "seems better."
5. If the task is ambiguous or the files contradict each other, STOP and ask. Do not guess.

---

## General Guidelines

These are hard rules. They override convenience.

- **Never use the em dash "—". Use a plain dash "-" instead.**
- **When writing commit messages, NEVER auto-add your agent name as co-author.**
- **Never manually modify auto-generated files** - `CHANGELOG.md`, lockfiles
  (`package-lock.json`, `uv.lock`, `poetry.lock`), or anything marked auto-generated.
- **When writing or substantially editing long Markdown files, put each full sentence on
  its own line.** Preserve normal Markdown structure, but avoid wrapping multiple sentences
  onto one physical line. This keeps diffs clean and reviewable.
- **When making technical decisions, do not give much weight to development cost.**
  Instead, prefer quality, simplicity, robustness, scalability, and long-term
  maintainability. This is a portfolio project - the code must be defensible in an
  interview, not merely functional.
- **When doing bug fixes, always start by reproducing the bug in an end-to-end setting**
  as closely aligned with how an end user hits it as possible. This makes sure you find the
  real problem so your fix actually solves it.
- **When end-to-end testing a product, be picky about the UI and be obsessed with pixel
  perfection.** If something clearly looks off - even if it is not directly related to what
  you are doing - try to get it fixed along the way.
- **Apply that same high standard to engineering excellence:** lint, test failures, and
  test flakiness. If you see one, even if it is not caused by what you are working on right
  now, still get it fixed.

---

## Workflow

### Before writing code
- Restate the goal in one sentence and name the checklist item it maps to.
- Identify every file you expect to touch. If a change spans backend and frontend, plan both
  sides before starting so the API contract stays consistent.
- Check whether stdlib or an already-installed package covers the need before adding a
  dependency (see `CLAUDE.md` → NEVER Do These Things).

### While writing code
- Match the existing structure in `CLAUDE.md` → Directory Structure exactly. Put files where
  the map says they go.
- Follow the language conventions in `CLAUDE.md` (Python conventions, TypeScript conventions).
  These are not suggestions.
- Keep the response envelope consistent: `{ "data": ... }` on success, `{ "error": "..." }`
  on failure. No exceptions.
- Every function should be explainable out loud in an interview. If you cannot explain why a
  line exists, it should not be there.

### After writing code
- Run the definition-of-done checklist below before claiming a task is complete.
- Update the **Build Checklist** in `CLAUDE.md` - check off what you finished.
- If you changed the schema, endpoints, a convention, or a pipeline decision, update the
  relevant file (`CLAUDE.md` or `PIPELINE.md`) in the same change so the docs never drift
  from the code. A future reset of you will read the docs, not the git history.

---

## Definition of Done

A task is NOT done until all of these are true. Do not report completion otherwise.

This project has two kinds of task. Backend/API and frontend tasks are verified the ordinary
way - run it, inspect it. Pipeline tasks (anything in `PIPELINE.md`) have correctness that
lives in numbers over time, which running-without-error does not prove. Those get an extra
check. Use the checklist that matches the task.

**Backend / API task:**
- [ ] Endpoint returns the correct status code and envelope for the happy path.
- [ ] Every documented error case returns the correct status (400 / 401 / 403 / 404 / 500).
- [ ] Verified with an actual `curl` command - paste the command and its output.
- [ ] Every error is handled - no bare `except:`, no swallowed exceptions.
- [ ] No secrets in source. Config comes from `.env`.
- [ ] Relevant checklist item in `CLAUDE.md` is checked off.

**Frontend task:**
- [ ] Screen/flow renders and the full user flow works in the browser.
- [ ] All API calls go through `services/api.ts`. No raw `fetch()` in components.
- [ ] No `any` types. Unknown shapes get a defined interface.
- [ ] Token access uses the pattern in `CLAUDE.md` (httpOnly cookie), never `localStorage`.
- [ ] UI is checked for pixel-level issues - alignment, spacing, loading and empty states.
- [ ] Relevant checklist item in `CLAUDE.md` is checked off.

**Pipeline task (pose, CoG, smoothing, move classification, scoring):**
- [ ] The stage runs end-to-end on a real sample clip, not just a synthetic unit input.
- [ ] You reasoned through correctness explicitly and wrote the reasoning in the PR/summary:
      e.g. mass fractions sum to 1.0, the weighted average is implemented right, output sits
      in a physically sane location on the frame.
- [ ] **Regression guard:** because correctness here is numbers a future reset of you cannot
      re-derive by reading code, save the sample clip and this stage's output to
      `pipeline/fixtures/` (see `PIPELINE.md` → Fixtures). One clip is enough. This is how a
      later session detects that an upstream change silently moved these numbers.
- [ ] Relevant checklist item in `CLAUDE.md` is checked off.

---

## Testing Expectations

- Backend endpoints are proven with `curl` before you call them done.
- For any bug fix, reproduce the bug end-to-end FIRST, then fix, then confirm the
  reproduction now passes.
- Do not leave failing or flaky tests behind, even ones you did not write. Fix them or flag
  them explicitly.
- Test the unhappy paths, not just the happy one: unauthenticated request, a clip that is
  too long, a clip where no person is detected, holds annotated out of order, a video the
  pose model produces low-confidence landmarks for.
- For pipeline stages, "test" means the regression-guard fixture above plus your written
  correctness reasoning. Do not invent a heavyweight golden-file harness the PRD does not ask
  for - one saved clip and output per numbers-heavy stage is the bar.

---

## Guardrails - Ask Before You Act

STOP and ask the user before doing any of these:

- Changing the database schema (column names, types, tables).
- Changing an API endpoint's path, method, request shape, or response shape.
- Changing a **Settled Decision** in `CLAUDE.md` or `PIPELINE.md` (e.g. swapping segmental
  CoG for hip-midpoint, or auto-detecting holds instead of user annotation).
- Adding a new third-party dependency, model, or service.
- Anything listed under **Deferred - Do Not Build** in `CLAUDE.md` or **Out of Scope - V1**
  in `PRD.md`. Scope creep is a defect.
- Deleting data or writing a destructive migration.
- Modifying `.env` handling or anything touching secrets.

When in doubt, prefer a short question over a wrong assumption. A memoryless agent that
guesses wrong is worse than one that asks. This matters more here than in a normal project:
many of the settled decisions look suboptimal from inside a single file and are correct only
with context you no longer have after a reset. The files hold that context. Trust them.

---

## Commits

- One logical change per commit. Keep the diff reviewable.
- Message format: imperative mood, present tense - `add segmental center-of-mass calc`,
  not `added` or `adds`.
- Do NOT add the agent as co-author or add any "Generated by" trailer.
- Never commit `.env`, secrets, sample videos with real faces you lack rights to, or
  auto-generated files as if they were hand-written.

---

## Interaction Style

- This app doubles as an interview portfolio piece. Optimize for correctness and clarity
  over speed.
- When you finish, summarize what changed, what you verified, and what remains - in that
  order, briefly.
- If you notice something off that is out of scope for the current task, note it clearly
  rather than silently expanding scope, unless it is a trivial fix aligned with the
  General Guidelines above.
