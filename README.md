# OptimalClimbing

A web app that analyzes a video of a rock climb and gives per-move, technique-focused
feedback, centered on the climber's center of mass relative to the holds.

---

## If you are an AI agent starting a session, read this first

You have no memory across context resets. These docs are your durable memory. Read them in
this order before doing anything, every session:

1. **`PRD.md`** - what the product is and why. The product source of truth. Start here to
   understand the goal.
2. **`CLAUDE.md`** - the technical map: stack, schema, endpoints, conventions, and two
   sections that exist specifically for a reset agent: **Settled Decisions** and
   **Deferred - Do Not Build**. Read those twice. They pre-answer the "wouldn't X be simpler?"
   temptations that a fresh context reliably has and that are usually wrong here.
3. **`PIPELINE.md`** - how the analysis core works (pose → center of mass → smoothing → move
   classification → scoring → feedback), with the math to rebuild any stage. Read before
   touching anything in `frontend/src/pipeline/` or `backend/feedback/`.
4. **`AGENTS.md`** - how to behave: workflow, guardrails, and the Definition of Done. Read
   before writing code.

Then find your task in the **Build Checklist** at the bottom of `CLAUDE.md`. That checklist is
your resumable state - it tells you what is already done. Do not rely on git history; a fresh
context cannot.

## Which file answers what

| Question                                                        | File          |
|-----------------------------------------------------------------|---------------|
| What are we building and why? What is in / out of scope?         | `PRD.md`      |
| Where does this code go? What is the schema / endpoint / stack?  | `CLAUDE.md`   |
| What was already decided, and what must I not build?             | `CLAUDE.md`   |
| How does the center-of-mass / move-classification math work?     | `PIPELINE.md` |
| How do I behave, verify, and know when a task is done?           | `AGENTS.md`   |
| How do I build a pipeline stage consistently?                    | `skills/pipeline-stage/SKILL.md` |

## The two things a reset agent gets wrong most often

1. **Re-deciding a settled choice** because it looks re-decidable from inside one file (e.g.
   using the hip midpoint for center of mass, or auto-detecting holds). Do not. See
   `CLAUDE.md` → Settled Decisions. Changing one is a guardrail item - ask first.
2. **Pulling in deferred scope** because it seems easy or better (the gym map, depth scoring).
   Do not scaffold it. See `CLAUDE.md` → Deferred - Do Not Build.

## Build order (do not skip ahead)

Analysis core first, proven on real footage → product shell → deploy and test with real
climbers. The social / gym-map layer is a real future direction but is NOT V1 and has no files
yet. Details in `PRD.md` → Build Phases.
