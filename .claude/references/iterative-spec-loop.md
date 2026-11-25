# Iterative Spec Loop — strategy → per-increment build, without re-running the standup chain

When a surface already has a **living spec**, each new iteration ("increment") should NOT re-run the full
`mybrain` design-doc → `doc-coauthoring` → `Plan` spec-doc chain. That chain is the **one-time standup cost**;
afterward you run the cheap per-increment loop. `mybrain`'s **Iterate mode** (SKILL.md § Iterate Mode Process) carries the
one-line loop summary + gate summary and points here; this reference holds the per-step executable detail, gate
examples, the rationale, the living-spec definition, gate calibration, and the doc mechanics that reconcile it with
`impag`'s per-stage-plan-files rule.

## What a "living spec" is

A single doc per surface holding only: the **north star** (complex end target), **binding constraints**, an
**unordered backlog** of candidate increments, and a **✅-shipped log** (one line per shipped increment + commits). It is
an INDEX, not a plan — it never carries full build detail. private-app's
a private design note is the reference shape: north star · build principle ·
current-increment detail that collapses to a ✅ line on ship · candidate-next-increments backlog · binding constraints ·
open calls parked.

Standing one UP is still Quick/Deep mode — the divergent design work that produces the north star + backlog.
You do it **once per surface**.

## Executable per-increment loop

Run this instead of re-running the design-doc → spec-doc chain.

1. **Re-pick.** Read the backlog; per candidate note what it teaches/unblocks and which parked "open call" it touches. Confirm the user's increment or recommend one.
   First collapse any increment `impag` archived since the last run: its backlog entry → one-line ✅ + commits.
2. **Design gate** (below): fires → run it first; else → straight to step 3.
3. **Detail into a per-increment file.** Template on the last shipped increment's section; write a thin `docs/plans/YYYY-MM-DD-<increment>-spec.md` (goals, chosen approach, visible acceptance, out-of-scope).
   Add a one-line backlog pointer to it in the living spec; do NOT inline build detail there. This thin pass replaces the `doc-coauthoring` + `Plan` two-hop.
   Pull the increment's slice from `docs/strategy/` when that is the surface's source of truth.
4. **Hand off:** `/qimpag docs/plans/<increment>-spec.md` -- `impag`'s plan-authoring pass grounds the increment against code, locks decisions in that file, then builds.
5. **Collapse on ship:** `impag` step 8a archives the per-increment file; the ✅ line is step 1's job next run.

**Design gate** -- criteria → mybrain SKILL.md §Iterate Mode Process. Examples: new seam = new data source, state store, cross-region layer; unsettled = >1 plausible way to build it.

## Design-gate calibration (worked example)

Gate calibration:

Worked on private-app's backlog: *read-only method cards* / mechanical *active-5 overlays* → no gate, straight
to qimpag. *Greenfield feed engine (#R1)* / *scenario mode* → gate fires (new feed engine / new interaction
model), so `mybrain`-quick first.

## Doc mechanics — reconciling with impag's per-stage-plan-files rule

The hybrid shape dissolves the apparent tension:

- **Living spec** = the "growing design doc" `impag`'s rules tell you NOT to append stages to. Keep it a
  north-star + backlog + ✅ index.
- **Per-increment file** = the "separate `docs/plans/` file" `impag`'s rules ALLOW. It is single-increment,
  `impag` grounds + stages IN it (like iteration 1), and it **archives on ship** — so it never grows across
  iterations and never becomes a re-read tax.

So `impag`'s plan-authoring pass, when its target IS a per-increment iteration spec, grounds **in place** rather
than spawning yet another file. `impag`'s rule was narrowed 2026-08-08 to *a new file only when a session that
is not executing the stage would otherwise re-read its plan* — the per-increment file clears that: inlined, the
detail would be re-read by every later Iterate session reading the living spec, none executing it; read the living spec as the index
and the per-increment file as the plan.

## Why the chain isn't per-iteration

The heavy chain exists to do divergent design work — approach comparison, architecture assessment, ideation.
A rich strategy layer + a living spec have already settled that for the surface as a whole. Per increment you owe
only: which slice next, any increment-local design (the gate), and a buildable detailing. Re-running the standup
chain each increment re-pays a one-time cost — the "token waste" this loop removes.
