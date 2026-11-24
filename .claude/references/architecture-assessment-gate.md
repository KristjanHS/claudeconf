# Architecture-assessment gate

Load this when a planning session's cheap inline gate has decided a **refactor-first
assessment is warranted** (see the checklist below) — i.e. you're about to either
dispatch `Plan` or assess inline. Callers: `mybrain` step 2.6, `impag` step 1's
plan-authoring pass. Not loaded for greenfield/isolated work.

The point of the gate: make the refactor-before-feature call **deliberately and
early**, presented to the user as alternatives — not discovered late as rework.

## Two decisions, kept separate

**1. Should we assess refactor-first at all?** (cheap, inline, no dispatch)

Skip when the feature is greenfield or lands behind a clean new interface with no
existing callers — say so in one line and proceed. Skip, too, when the design doc
**already records a refactor decision** from a prior mybrain 2.6 / plan-authoring pass —
confirm and honor it, don't re-open. Otherwise assess if **≥1** holds:

- **Shotgun surgery** — one conceptual change touches ≥3 existing files/modules.
- **Rule-of-three duplication** — the idea is "like X but…" and this is the 2nd/3rd
  near-duplicate of an existing pattern, not an extraction.
- **New shared-seam consumer** — adds a reader/writer to an existing data model, state
  store, auth path, or event bus not designed for multiple consumers.
- **Hedge language** — the idea/design doc itself says "not sure where this fits" /
  "might conflict with X".

**2. Who does the assessment?** — follow the **existing delegation gate**, don't invent
a trigger:

| Dispatch `Plan` (opus/medium, pinned) | Assess inline (no dispatch) |
|---|---|
| Authoring a multi-stage execution plan from scratch (`Plan`'s literal job) | The deliverable is a scoring matrix the caller already produces natively |
| Assessment needs a subsystem **not in the caller's context**, at polluting depth | Facts already in context **and** caller is Opus-capable + interactive (mybrain) |
| Caller is **full-auto** (impag), whose discipline forbids inline bulk reads | You'd be firing `Plan` to "use Plan," not because a fresh deep-read is needed |
| High blast-radius / hard-to-reverse — fresh-context Opus judgment de-risks | Greenfield / isolated |

Dispatching `Plan` when the facts are already in an interactive Opus caller's context,
or just to produce a matrix the caller builds anyway, is **ceremony** — it re-reads what
you hold and trains the gate into noise. Reserve it for a genuine fresh deep-read.

## `Plan` brief templates

**A — impag authoring a plan (dispatch is the default here).** After the Explore/Haiku
recon brief lands (impag step 1a), dispatch `Plan`:

> Author a staged, pinned implementation plan for <target> from the recon brief below
> (do NOT re-read the whole subsystem; the brief is your ground truth, grep only for
> gaps). Last stage = full verify + live e2e + review. Include a **required
> "Refactor-first assessment" section** (contract below). Return the plan as the doc
> body; cite `file:line` for every claim about existing code.
> [paste recon brief]

**B — mybrain grounding a decision (dispatch only when the subsystem isn't in
context).** mybrain builds and presents the matrix itself — dispatch only for facts:

> Read <subsystem> and answer, with `file:line` evidence, ONLY the Refactor-first
> assessment contract below for adding <feature>. Do not propose feature approaches or
> build a scoring matrix — return the raw assessment; the caller scores and presents it.

## Refactor-first assessment — output contract

Whoever produces it (Plan, or mybrain inline) returns:

- **Verdict**: refactor-before-feature needed? yes / no / unclear.
- **2-3 alternatives**, each: short label, one-line description, depth
  (none / targeted-refactor-of-X / broader-restructuring-of-Y), effort (Low/Med/High),
  and the concrete `file:line` evidence tying it to whichever signal(s) fired.
- **Recommendation** + one-line rationale.
- **Fallback**: if the verdict is genuinely *unclear* (evidence thin, both directions
  plausible), do NOT force a false-precise answer — surface "unclear — recommend a
  scoped spike to de-risk" as its own alternative.

**Verify each alternative's premises before presenting them.** An alternative's cost/risk
description is a factual claim that steers the user's pick; a wrong one buys a decision made
on a false premise. When an alternative rests on an unchecked fact ("these constants have no
TS source", "this edit is behaviour-preserving"), grep the anchor first — or write it to state
the uncertainty rather than resolve it. Resolving a `[AUDIT]` premise can leave the
*recommendation* standing while replacing its *rationale*; present the corrected reason, not
the inherited one.

**The artifact-attribution justification (a refactor reason that isn't reuse).** When the code
under change emits a **committed or published artifact** (a calibration/lockfile/snapshot/golden
that downstream consumers read), a commit that both restructures a code path and changes what it
computes makes the artifact diff *unattributable* — a refactor bug and the intended behaviour
change look identical. Splitting them, with the refactor stage gated on a **byte-identical
artifact**, is what makes the next diff falsifiable. This can justify a **one-caller extraction**
that a no-N=2-abstractions rule would otherwise reject: the boundary's deliverable is a provable
no-op checkpoint, not reuse. Name it explicitly — "cleanliness" understates it and loses the
argument. It binds hardest when the follow-on stage ships to production.

**Presentation.** mybrain maps the alternatives onto its existing evaluation matrix
(`mybrain/SKILL.md` step 4) and presents them via `AskUserQuestion` *before* proposing
feature approaches — the chosen depth reshapes which approaches make sense. impag cannot
auto-pick: it persists the alternatives into the plan doc as a `[USER DECISION]` block,
points Next-action at it, and defers via its existing user-decision path (its questions
happen later, in the chained `qimpag` session).

## Why (citations)

- **Rule of three** — refactor on the 3rd near-duplicate, not the 2nd; premature
  abstraction is worse than duplication. <https://en.wikipedia.org/wiki/Rule_of_three_(computer_programming)>
- **Shotgun surgery / divergent change** — one change rippling across many
  files/modules is the smell that a refactor should precede the next feature.
  <https://refactoring.guru/smells/shotgun-surgery> · <https://refactoring.guru/smells/divergent-change>
- **ADR trigger criteria** — assess when a decision is architecturally significant or
  hard to reverse; *skip* when limited in scope/risk/cost or already covered. The gate's
  skip rule mirrors this. <https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html>

## Sync note

The four signals + skip rule are inlined in `mybrain/SKILL.md` step 2.6.
`impag/SKILL.md` step 1's plan-authoring pass *references* this gate rather than
inlining it (it delegates the assessment to `Plan`, which reads this file). Edit the
signals here first, then sync mybrain 2.6 (same discipline as the bootstrap.bats /
README sync note in the dotfiles root `CLAUDE.md`).
