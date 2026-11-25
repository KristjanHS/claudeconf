# mybrain — deep dives

Conditional/abnormal-only sub-procedures for the `mybrain` skill that are **mybrain-exclusive**. The body (`mybrain/SKILL.md`) holds every normal-path directive plus the gate that decides whether a branch here fires; nothing here repeats a body directive.
**Read it only when a step points here and its gate has fired.** A Quick-mode run that skips spec review and dispatches nothing never needs this file. **Read SCOPED**: `grep -n '^## '` for the section the body pointer names, then Read only that section — never full-read.

Shared references keep their own files (multiple skills/rules point at them): ideation technique playbooks + Deep-mode phases → `ideation-techniques-library.md`; the Iterate-mode loop → `iterative-spec-loop.md`; the step-2.6 contract → `architecture-assessment-gate.md`; the step-7 check-6 payload → `spec-rework-audit.md`; dispatch cost model → `subagent-dispatch.md`.

---

## Spec review — reviewer brief (step 7)

Fires only when the step-7 review gate fires. `mybrain/SKILL.md` § 7 holds the gate and the skip-line.

**Do NOT review your own spec inline.** As its author you carry the rationalizations that produced it, so an inline pass rubber-stamps the assumptions most likely to be wrong.
Dispatch a **fresh sub-agent that did not write the doc** -- e.g. `Agent(subagent_type="code-reviewer")`, or a read-only `general-purpose` -- and have it review against the actual codebase.

Instruct the reviewer to **verify, not validate**: assume nothing in the doc is correct until checked against the real source, and return findings ordered by severity (Critical / Important / Nit) with `file:line` evidence and a RIGHT/WRONG verdict per claim.
Its checklist:

1. **Claim verification** -- every factual assertion the spec makes about the code (a field/function exists, a path behaves a certain way, "no migration needed", nothing else depends on the thing being changed) checked against source.
   Flag any that are WRONG or UNVERIFIED.
2. **Placeholder scan** -- any TBD, TODO, incomplete sections, or vague requirements?
3. **Internal consistency** -- do sections contradict each other? Does architecture match feature descriptions?
4. **Scope check** -- focused enough for a single implementation plan?
5. **Ambiguity check** -- could any requirement be interpreted two ways? Each must resolve to one explicit meaning.
6. **Re-work audit** -- only when the design carries a phased plan with ≥3 phases touching the same builder / sheet / module: procedure + rationale → `~/.claude/references/spec-rework-audit.md` (paste it into the reviewer brief when this check fires).

Fold the reviewer's corrections into the doc, then ask the user to review the written spec before proceeding.

## Model routing — sub-agent dispatch table

Fires only when a step actually dispatches. The always-true rule (main brainstorm on the session default; omit the `model` param; never `sonnet`) stays inline in `mybrain/SKILL.md` § Model routing.

| Sub-agent | Model | Why |
|-----------|-------|-----|
| **Architecture-assessment grounding** (step 2.6, only when the subsystem isn't in context) | **`Plan`** on its pinned **Opus/medium**; for a lighter grounding read, **`Explore`** (Haiku) when it's pure locate/"where is X", or **`general-purpose`** (opus/medium) when it must synthesize across the subsystem\* | Dispatched for *facts*, not the matrix; skip the dispatch entirely when facts are already in context |
| **Spec review** (step 7, `code-reviewer`) | **Opus/medium** (the pin) for routine designs; for high-blast-radius/risky ones raise `code-reviewer.md`'s `effort:` to `xhigh` for that run — there is no per-call effort param | Match to blast radius -- lower the effort for the routine gate, never the model |
| Spec review via read-only sub-agent | **`general-purpose`** (opus/medium) | It must *verify* claims against source, not just locate -- so `general-purpose`, not Haiku `Explore`\* |
| **External research** (step 1 / step 3, multi-source web or library comparison) | **`general-purpose`** (opus/medium) with web tools; the `deep-research` skill for a genuinely large multi-source question | Returns a synthesis, never raw pages.\* Skip the dispatch for a single verbatim lookup |
| **Ideation techniques** (Deep mode, step 2.5, dispatched in parallel) | **`general-purpose`** (opus/medium) | They explore divergently; they don't make cascading decisions -- `general-purpose` is the pinned opus/medium vehicle.\* Synthesis/convergence stays with the Opus-`high` main |

\* `Explore`'s effort pins to `low` and cannot be raised per-call, so `Explore`+`model:opus` yields opus/**low**. Anything that synthesizes or verifies routes to `general-purpose` instead.
