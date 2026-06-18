---
name: retro
description: Session retrospective — reflect on what was learned, update memories and project docs.
---

## 1. Lessons learned

3–6 bullets, ≤200 chars each. Non-obvious only — skip anything derivable from code or git.

## 2. Capture corrections

Route each correction or confirmed approach via `~/.claude/references/recording-principles.md` (§"When asked to record information"). All targets in those trees auto-load; do not invent new paths. Never create `feedback_*.md` — feedback is a temporary inbox; graduate into skills/rules/CLAUDE.md. **If no correction this session, this step is silent.**

## 3. Update project memories

**Short-circuit:** if `project_state.md` was updated earlier in this turn (e.g., by impag Step 7 stage-done), skip — do not restate. Only append if load-bearing facts from Steps 1–2 aren't covered by that earlier write.

When appending: prune while you go. These files are rolling snapshots, not logs — scan for overlap, merge bullets, delete sections now derivable from code/git/in-repo docs, supersede-and-delete outdated rules. Size budgets and archive-closed-plans procedure live in `references/writing-targets.md`.

## 4. CLAUDE.md / rules gaps

Scan the conversation for repeated corrections, misunderstandings, or missing context. If any, present as **Issue → Proposal → Target → Exact text**, then apply directly. Otherwise silent.

Routing: see `~/.claude/rules/instruction-file-discipline.md` (Tier discipline).

When writing a new rule or bullet, load `references/writing-targets.md` for rule-body schema, frontmatter spec, condense-if-over-budget (4b), and stale-rule sweep (4c) procedures. Don't proactively rewrite existing conformant rules.

## 5. Audit touched files

For files edited in Steps 2–4: merge lingering `feedback_*.md` into targets then delete; flag duplication (pick one home); flag negative framing ("don't X" → state what TO do). Structural findings too large for a rule → `<project>/docs/audits/`. Silent if no findings.

## 6. Context review

Run `token-usage context --brief` (global pip install — no `cd`). Print one line: `Context: X% · stop-buffer Y`. Propose fixes only if actionable (stale memory, oversized rules/skills, large reads, session-budget pressure).

## 7. Close

If Steps 2–5 produced writes, list them as `step: file +change` lines (max one per file). Otherwise emit `Memory/rules: none.` + the Step 6 one-liner and stop. No Report table — impag's branch report + `project_state.md` already hold commit/stage facts.
