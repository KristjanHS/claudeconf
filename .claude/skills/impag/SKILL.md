---
name: impag
description: Implement plan using parallel subagents. Full-auto — never stop to ask.
---

Implement plan using parallel subagents. Full-auto — never stop to ask.

$ARGUMENTS — plan file path (default: most recent in `docs/plans/`).

Remind user: "Use `--dangerously-skip-permissions` for uninterrupted execution."

## Process

1. **Load plan** — read plan file, identify all tasks and dependencies. If `memory/project_state.md` has a "Next action" pointing at a different plan than the default (most-recent), prefer that pointer. If that plan is fully COMPLETE, pull remaining work from its "Out-of-scope" / "Deferred" / "Nice-to-have" sections and announce the pivot. If no open work anywhere, stop and report state rather than inventing tasks.

   **Uncertainty markers first.** If the plan carries author-acknowledged hedges (`[AUDIT]`, `[likely cut]`, "may duplicate", "not sure whether"), surface them one line each *before* Stage 1 executes: "should X be resolved first, or proceed with the confident siblings?" The plan author's own doubt is the strongest "don't ship yet" signal available — don't ship past it silently.

2. **Evaluate plan size** — count implementation tasks (exclude docs-only/meta tasks).

   - **≤4 tasks**: proceed in one session.
   - **5+ tasks with a dependency chain**: identify a **stage boundary** after task 2–3 where code is testable and committable. Print: `"Plan has N tasks — splitting into Stage 1 (tasks 1–K) and Stage 2 (tasks K+1–N). Stage 2 runs in a fresh session."`
   - Stage boundary criteria: all code compiles, tests pass, no half-wired interfaces.
   - Execute only Stage 1. After final commit, save remaining tasks to `memory/project_state.md` AND append this verbatim sentinel on its own line (a machine-readable continuation marker — if you drive chained headless runs with a wrapper script, paraphrasing or markdown-formatting the line breaks the contract):

     ```
     <!-- impag-chain-next-stage -->
     ```

     A headless driver that re-fires `/impag` consumes the sentinel after each detection — re-emit it on every stage that should chain forward. Same rule on a budget-cap abort mid-stage (step 4f): if the stage's work is incomplete and another `/impag` invocation should resume it, append the sentinel so the chain re-fires.

3. **Execute tasks** — run in plan order, one subagent per task. Wait for each to complete before starting the next. No worktrees; subagents work on the main tree.

   **Parallel exception:** parallelize adjacent tasks only when independence is obvious without reading code — different dirs, one adds a new file while another modifies unrelated code, or the plan explicitly says "parallel". Serialize otherwise. After parallel work, run a cross-file consistency check (shared imports/signatures/fixtures the parallel agents each touched) before committing.

   **Research-style plans** (web research, analysis, docs — no code): dispatch each task with `subagent_type='Explore'` (read-only, summary-only return) and have it invoke a deep-research step first. Skip step 4's pytest/pyright and step 6's code-reviewer. Commit one consolidated doc.

   Dispatch each subagent with: implement Task N from [plan], run targeted tests + pyright covering the change, do NOT commit, work only on the task's focus files (may touch related imports/tests), report diff + ALL files touched + any issues.

4. **After each task** — orchestrator verifies then commits:
   a. Run `git status` + `git diff` to review changes.
   b. Check changed files against expected scope — revert out-of-scope files.
   c. Run **targeted tests** covering the task's focus files + `pyright`. Run full `pytest tests/ -q` only before the stage's final commit. `-v` only on failures.
   d. Commit with a message listing the completed task, then update `memory/project_state.md` with completed list + next task.
   e. Mark task done only after commit succeeds.
   f. **Context budget check.** If a budget warning fires (130k+ tokens), wrap up: save remaining tasks to `memory/project_state.md`, jump to step 6. Resumed sessions re-run from Step 1 (the plan is re-loaded). The completed-task list in `project_state.md` is what makes the resume idempotent — keep it accurate.

5. **Failed subagent** — do NOT fix manually. Dispatch a fresh fix subagent with the error details. If the fix subagent also fails, ask user.

6. **Final review** — dispatch the `code-reviewer` subagent with BASE_SHA..HEAD_SHA covering all changes. If `code-reviewer` is not a registered subagent type, announce the gap ("code-reviewer not available — dispatching `Explore` with a review prompt"), fall back to a read-only `Explore` review, and record the registration gap in the retro. Don't silently degrade.

7. **Fix review issues** — auto-fix Critical/Important issues by dispatching fix subagent(s) immediately, then re-verify. Only ask user if a fix fails twice on the same issue.

   **Stage-done timing:** at a stage boundary, the stage is NOT done when the last task's commit lands — it's done when review fixes (Critical/Important) have been committed and re-verified. Only then update `memory/project_state.md` with "Stage N complete" and queue `/retro`. If review returns only Nice-to-have findings, the stage is done as-is (record them as follow-ups).

   **Continuation sentinel (before Step 8).** If the plan's task list shows unexecuted stages after this one, append the canonical sentinel to `memory/project_state.md` on its own line — verbatim:

   ```
   <!-- impag-chain-next-stage -->
   ```

   Then verify with `grep -qE '^<!-- impag-chain-next-stage(: [1-9][0-9]*)? -->$' memory/project_state.md` — if it fails, the chain stops. (The grep tolerates a legacy `: N` suffix form some drivers still accept; prescribe the no-suffix form for new emits.) Updating "Next action" prose is **not** a substitute; a headless driver only re-fires on the canonical line. Stale "Next action" prose from earlier stages should also be rewritten so it doesn't trip a driver's paraphrase diagnostic.

8. **Finish the branch** — ALWAYS invoke the `finishing-a-development-branch` skill automatically. No prompt, no option — just run it. The skill returns control silently after its branch-state report; continue directly to step 9 in the same response. Do NOT end the turn; do NOT wait for user input. If the user wants to discard, they can type `discard` on the next turn.

9. **Retrospective** — ALWAYS invoke `/retro` automatically after step 8, **in the same turn**. No prompt, no option — just run it. Invoke at the **main conversation level** (via the Skill tool), NOT as a subagent — the retrospective needs full session context to update memories and docs accurately. Do not narrate the 7→8→9 transitions ("Now invoking…", "Proceeding to…") — invoke each skill directly; the tool call is the signal.

## Rules

- Before reverting out-of-scope files, check if they could be user edits from another window. If unsure, ask.
- Large tasks (4+ files, many small edits): prefer direct orchestrator edits — subagents can hit budget limits mid-task.
- Small tasks (1-2 files, <100 LOC of diff, clear specs): prefer direct orchestrator edits — subagent overhead exceeds the edit cost. Reserve subagents for work large enough that keeping it out of orchestrator context has real payoff.
- Session limits: the step 4f budget check is the primary mechanism — run it after every commit. The ~120-turn / "context feels heavy" heuristic is a coarser fallback: if either trips, finish the current task, commit, and stop. In both cases, the stage still owes review (step 6) + fixes (step 7) + finish-branch (step 8) + retro (step 9) before handoff — don't skip them to save one more task.
- **External-ecosystem constants warrant a pre-ship check.** When a plan quotes a specific numeric constant tied to Anthropic/Claude Code internals (autocompact thresholds, cache TTLs, default timeouts, retention counts), spend one web-search before shipping to confirm the value is still consensus. Plans age faster than library code; a 2026-Q1 value can be obsolete by Q3 and the cost of verification is ~1 turn vs. shipping a silently-degraded threshold.
