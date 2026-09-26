# Information Recording Principles

Whether an unasked line is written at all → `~/.claude/rules/prose-budget.md` §Every add pairs with a delete. This file covers only the **asked** write: where it goes.

## What belongs in L1 (CLAUDE.md content types)

| Type | Example |
|------|---------|
| Iron rules / prohibitions | Never run Windows exes from WSL; never hardcode calculated values |
| Core commands | `python -m edf_budget init` |
| Workflow constraints | Absolute paths for all tool calls |
| Error diagnostics | Symptom → cause → fix |
| Code patterns | Copy-paste ready snippets |
| Directory map | Function → file |
| Trigger indexes | Pointers to L2 docs |

## When asked to record information

L1/L2/L3 — what each tier is, where it lives and when it loads → `~/.claude/rules/instruction-file-discipline.md` §Tier discipline, already loaded whenever this question comes up.

1. High-frequency or iron-rule? → CLAUDE.md (L1) at matching scope
2. Multi-step workflow tied to a user trigger, ≥3 steps a CLAUDE.md bullet can't capture? → SKILL.md at matching scope (description always indexed; body loads on description match)
3. Domain-specific workflow tied to file types? → `~/.claude/rules/` with `paths` frontmatter (global only)
4. Detailed SOP / edge case / reference, or a project incident archive? → `./docs/*.md` (project) or `~/.claude/references/*.md` (global), never L2 — every entry needs a **trigger condition** (when to read it)

**Feedback/corrections → `type: feedback` staging file, then graduate**: capture + lifecycle/drain rules → `~/.claude/references/memory-system.md §Graduation routing`.

---

*The two sections below are the on-demand deep-dives for `~/.claude/rules/instruction-file-discipline.md` — pulled when authoring a SKILL.md, or running the pre-commit self-review.*

## SKILL.md authoring discipline

A SKILL.md body loads into the session prefix the moment the skill matches and stays there for the rest of the session — body bloat is *more* expensive than CLAUDE.md bloat. A 200-line skill body is a heavier ongoing cost than a 200-line rule file (which only loads on path match), so apply tier discipline asymmetrically.

**A NEW skill body carries the workflow steps plus the minimum trigger logic, and nothing else** — no size target, because there is no number to enforce or aim at. Detailed playbooks (technique libraries, anti-pattern tables, installation procedures) go to L3 references, linked from the body. What keeps a body short is that everything a normal run doesn't need was written to a reference instead.

**No SKILL.md carries an enforced budget, and nothing measures a body** → `memory-system.md §No size caps`. For an over-long body the remedy is **author's judgment**, and the first option is Anthropic's own: split into a reference. The lever is fewer body steps that each change behavior, not a byte ceiling.

**Don't include:**
- "Quick Reference" / "Summary Table" sections that restate the body in compressed form. Pick one representation, not both.
- "Common Commands" / "Quick Start" sections listing tool invocations the *user* (not Claude) runs — that's tool documentation, not skill behavior.
- "Related Skills" / "Getting Help" / "Why this matters" trailers — pure word count, no behavior. If a related skill is genuinely needed, name it inline at the trigger point.
- Agent SDK code blocks (`Agent({...})`, `await Task(...)`, `FleetManager.coordinate(...)`, memory-namespace trees). These don't execute from skill bodies — they're cargo-cult residue from agentic-QE playbooks.
- UI/output-formatting implementation (ANSI palettes, contrast ratios, escape codes). Belongs in the script that emits the output.
- Harness-internals docs (PostToolUse mechanics, cache TTLs, statusline thresholds). Document those in the hook script or a dedicated reference.
- Closing "Remember" / "Notes" / "Important" / motivational prose after the last actionable step. Skills end at the final step; anything after is restated body or vibes — both pure cost.

**Description field:** one-line trigger language. No "Examples:" lists or "e.g., …" elaboration — those bloat the always-indexed description and add no behavior.

## Pre-commit self-review checklist

After editing CLAUDE.md or a rule/reference file, before commit:

1. Anything in the diff already covered by a path-gated rule? → delete the duplicate.
2. Any new bullet naming a project-specific incident (file:line, date, project-only path)? → move to that project's rule.
3. 3+ bullets in a row sharing a shape? → extract to a reference, leave one pointer.
4. Did this edit add a sibling to a list now ≥4 items of the same kind? → extract the whole list.
5. Does every project-convention name still match current state? → grep to confirm.

If yes to any: revise before commit. The `condense` skill exists because this discipline wasn't applied at write-time — cheaper to apply now than to clean up later.
