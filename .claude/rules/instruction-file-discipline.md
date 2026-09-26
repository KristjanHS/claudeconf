---
name: Instruction file content discipline
description: Content discipline for CLAUDE.md, .claude/rules/**, .claude/references/**, and SKILL.md — prevent bloat that requires later condensation
paths:
  - "**/CLAUDE.md"
  - "**/.claude/CLAUDE.md"
  - "**/.claude/rules/**/*.md"
  - "**/.claude/references/**/*.md"
  - "**/SKILL.md"
---

# Instruction File Content Discipline

Cadence (ship vs batch) → `claude-md-edits.md`. This rule covers **content quality** — what belongs at which tier, and what to check before adding a bullet.

This file owns the write-time directives — execute them from here. `~/.claude/references/recording-principles.md` owns the routing tables (project × global, L1 content types) and SKILL.md authoring; open it when routing a line to a tier or authoring a skill, not to run the checks below.

## Top three anti-patterns

1. **"Why this rule exists" as a default template.** Optional — add only when the rule text doesn't convey the reason.
2. **Append-without-grep.** New bullets land beside near-duplicates. Grep the target first, then: **one** near-duplicate → `Edit` that bullet to absorb the new content, never append beside it; **two or more** → append, note the overlap, stop — merging ≥2 bullets is a `condense` pass with user approval, never mid-run. `/retro` does not condense. The two counts do different jobs: ≥2 near-duplicates means *don't merge now*; ≥3 overlapping bullets in a section is what triggers *running* the pass (§Delta-update).
   Binds **numbered taxonomy entries in an L3 archive** identically, not just rule bullets. Before minting class N+1, grep the file for the nearest existing class. **If the draft would say "same family as §X", "same shape as §X", or "§X asks … this class is the next question", it IS §X** — Edit §X to absorb the new angle. A cross-reference between two classes is the merge signal, not a substitute for merging. **The tell is any phrase naming §X as the same defect under a different trigger, however worded** — "sibling/cousin of §X", "the inverse form", "§X is the silent form, this is the loud one" all route around the list above while satisfying it in substance. Mechanical form, so wording cannot dodge it: **a draft body that cites another class by ordinal at all defaults to a MERGE**, and minting instead owes one sentence in the commit message naming the verification MOVE that differs — a different incident is not a different move.
3. **Project-specific rationale in global rules.** Stranger test — "would this make sense to a stranger with no knowledge of project X?" A "Why" naming a date / `file.py:line` / project-only path means the rule belongs in *that project's* `.claude/rules/`. Global rules carry the *generic* habit; the incident lives where it happened — in a commit message or the project's own rule file, never in a global rule.

## Tier discipline (L1 / L2 / L3)

- **L1** = `CLAUDE.md` — always loaded. Cross-cutting habits + pointers. (What each layer may ADMIT → `~/.claude/references/memory-system.md §Roles table`.)
- **L2** = `.claude/rules/**/*.md` — path-gated; loads only when matching files read/edited. Topic-specific operational rules.
- **L3** = `.claude/references/**/*.md` global, `docs/*.md` project — on-demand; loads only when an L1/L2 pointer fires. Long checklists, postmortems, recovery procedures.

**Rules:**
- L1 bullet that's path-specific (Python, hooks, openpyxl) → move to L2.
- L1 bullet that's a >3-sentence checklist or postmortem → move to L3, leave a 1-line pointer.
- **Move only reference-shaped content to L3 — never a directive, and never how-to a normal run needs to execute the step.** Test each pointer: *would a normal run open this to proceed, for this skill alone?* Yes → the split saves nothing; inline it with its directive. L3 earns its keep only for what a normal run never touches — **rationale/why, postmortems, abnormal-only branches** (a branch some runs skip is NOT abnormal — test each arm) — plus two carve-outs where the load lands off the normal reader: a **dispatched-subagent** payload, and **how-to ≥3 skills would otherwise duplicate** (per the ≥3-bullet rule below). Test each arm separately: if a run that takes this arm needs the text to proceed, it stays inline, however rare the arm.
- L2 rule that exists in both global and project with similar content → consolidate at the narrower tier (project usually wins; global only if truly cross-project).
- **Project-specific incident *archives* go to L3 (`docs/` or `~/.claude/references/`), NOT L2 (`.claude/rules/`).** Archives carry the history (anti-pattern 3: rules carry the generic habit). Route via the project's `CLAUDE.md` trigger table instead.
- **When one incident lands at both L2 and L3, split by kind, never by detail level.** L2 owns the directive *and* the verbatim command; L3 owns only what L2 dropped — the rationale and the incident. **The L3 entry may not restate the command or the directive.** Check: delete the L3 entry's first paragraph — if the L2 rule still tells you what to do, that paragraph was duplication.
- **Never restate a path-gated rule in CLAUDE.md.** Before adding an L1 Efficiency/Iron Rule bullet, grep `~/.claude/rules/` and `<project>/.claude/rules/` for the topic; if a rule covers it, keep one tier and delete the other (usually keep L2 and skip the L1 addition). Never both — the L1 copy always-loads, drifts, and wins.

## Multi-bullet shape pattern → extract to reference

When **≥3 bullets share a checklist shape** (pre-flight sweeps, debugging workflows, removal patterns, recovery procedures), extract to a single L3 reference and replace with one L1 pointer. The pointer carries the trigger language; the details live where they don't burn always-loaded tokens.

## Write-time checks

Whether a line is written at all → `prose-budget.md` §Every add pairs with a delete. These are the checks a line must also clear once it *is* being written.

- **Stale-name sweep.** When a bullet names a project convention (file paths, branch names, env vars), grep the current state before committing — pasted content may carry a name the project no longer uses. Same for asserted **state**: an instruction file may name a symbol as an example but must not assert what the tree currently does with it (counts, which arm runs, what a comment says). If a class genuinely needs the current behaviour, it owes a pinned falsifier or an explicit `as of <date>, unpinned` marker — an archive is never re-read, so nothing else will catch the rot.
- **A rule's `paths:` must cover every file EXTENSION its own rows govern.** A rule gated `content/**/*.md` whose admission table has a row for a `.json` file is structurally inert exactly where it is needed — the gate can never fire on the file it governs. Write-time check: list the file types each row names, and confirm one glob matches each; a row with no matching glob is either mis-gated or belongs in another rule.
- **Never put a COUNT in a pointer.** "the full 17-class taxonomy", "all 8 handlers", "the 5 checks" — a count is a coverage claim that no test pins and that the next append silently falsifies. Write "the full taxonomy". If the count is genuinely load-bearing (a deploy cap, an API surface), it owes a test, not prose.
- **Symmetric verbs.** For every `add` / `grep` / `record` / `document` add-verb in a checklist, pair a concrete subtract-verb (`delete` / `remove` / `unlink`). Asymmetric verbs generate one-way bloat — dead entries accumulate forever. Scan each numbered step: if it only grows the artifact, add a sibling step that prunes it.
  **This binds a FILE'S OWN write rules, not only a checklist you are authoring** — the self-application everyone skips. A doc that states how to add to it states how to drain it, **at the same trigger as the add** (a ship, a merge, a touch — never a size and never a schedule, which §No size caps bans).
  **Same trigger means the same EVENT at the same RATE — check the two against each other, not just that both exist.** A drain keyed to an event that is a strict subset of the add event (add on *any review*, drain on *the fix shipping*; add on *any session*, drain on *the plan closing*) is not a pairing: it licenses unbounded growth at the difference of the two rates, which is exactly the bloat the rule names. When the rates cannot be made equal, the fix is to **refuse the add**, never to write a drain that fires less often.
- **The second copy of a directive carries the imperative plus a cross-file `§` pointer, nothing more.** When a directive must appear at two trigger points, the copy at the second point may not carry the mechanism, the regen sequence, or the incident — both copies keep the trigger, one keeps the how.
- **An assistant-owed work item never lives in a rule file.** A rule is a standing directive; a work item parked in one is invisible to every backlog sweep. Route it to the project's backlog instead.
- **A line fits its target layer's canonical body and carries nothing else** — rule = the canonical rule body (`memory-system.md` §Canonical rule body); archive entry = heading + move; backlog entry = ⚠ / seam / falsifier; memory = one bullet naming its doc. A draft needing more than the shape is at the wrong layer, not entitled to a longer entry — what goes in is that document's name. Subtract-verb: **an entry whose defect a test now pins is deleted**, the test named in the commit message.
  **Every shape above is a FORM test, and form is free — clearing it is necessary, never sufficient.** Any nitpick spells as ⚠ / seam / falsifier, so a gate made only of that shape admits everything offered to it. The VALUE test runs first → `prose-budget.md` §Three admitted kinds.

## Delta-update, never rewrite

Append a new bullet/section, or Edit the specific line that's wrong — a narrow `old_string`, never rewriting the surrounding paragraph to accommodate the fix. Never regenerate the file or rewrite a section wholesale — each bullet is the residue of a specific incident, and "says the same thing more cleanly" silently drops that history. `Write` is for new files only; a `Write` over an existing instruction file is a rewrite by another name.

Cleanup spanning multiple bullets → stop. That's a `condense` pass, run as its own task with per-item user approval, triggered when a section accumulates ≥3 bullets overlapping in scope — dedup is the second half of this rule, not optional. What must survive is the **directive, not its narration**. Verify per section against `git show HEAD:<file>`, never against a line count. Five moves are pre-authorised, but only on text that first clears the **keep-test** — **read `instruction-file-discipline-deep-dives.md` §The five pre-authorised condense moves before the first cut**; both lists live there.

---

**Authoring a SKILL.md, or running the pre-commit self-review before committing an instruction-file edit?** → read `~/.claude/references/recording-principles.md` (§ SKILL.md authoring discipline — what a body admits + the don't-include list; § Pre-commit self-review checklist — the diff sweep).

**No size gate on ANY instruction file, memory file or doc**, and nothing measures a FILE to decide whether to open it — never `wc -c` one, never open one to trim it because it "looks big", and **never condense one mid-run** (note it and move on). The caps' removal, its rationale and the single `condense` carve-out → `memory-system.md §No size caps`.
