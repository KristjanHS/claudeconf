---
name: impag
description: Implement a plan full-auto; never stop to ask.
---

$ARGUMENTS — plan file path (default: most recent in `docs/plans/`).

Deep dives → `~/.claude/references/impag-deep-dives.md` (abnormal conditions only): `grep -n '^## '`, then Read one section.

## Process

1. **Load plan — scoped.** Read only the target stage (grep `^##` headers) or, in a roadmap, grep the item. Never full-read either shape. Identify tasks + dependencies.
   - Target: the "Next action" pointer, else the most-recent plan in `docs/plans/`; a user-typed plan arg beats the pointer. A `retro owed: <items>` marker runs first (scoped `/retro`, then clear it).
   - The pointer wins on the target, not its facts: on resume, reconcile every live claim against its falsifier.
   - Is the plan a live sibling's? Check before the questions round and long dispatches: `git log --format='%h %ci %s' -5 -- <plan> <edit sites>`; fresh commits from another session → next plan or ask, never duplicate it.
   - Plan COMPLETE or `Status:` CLOSED/SHIPPED → archive it now per step 8a (this session's first commit, not a finding), then announce the pivot to its deferred work. No open work → report; never invent tasks.
   - No executable plan, or work lacking focus files + committable boundaries (`Stage N.M`) → author one, don't execute (the plan-authoring pass): (a) recon via `Explore` only; (b) `Plan` authors the staged plan from that brief, never synthesize it in the orchestrator, with a Refactor-first assessment unless its skip test fires (say so) and a last stage of full verify + live e2e + review; (c) a new `docs/plans/` file back-linked from the rung in the same commit (`→ plan: docs/plans/<name>.md`); never re-plan or re-execute it. (→ deep-dives §Step 1 — plan-authoring pass.)
     A genuine refactor decision is USER-OWNED: persist a `[USER DECISION]` block, point Next-action at it, STOP without arming the chain. Otherwise commit the plan, arm the sentinel at Stage 1, update Next-action, STOP.
   - Ambiguous target → defer to `/qimpag` (or fold it into that run's questions round); never guess. An unfinished plan is not ambiguous: resume it, never offer a which-phase-next fork.
   - Surface plan hedges before Stage 1, one line each (`[AUDIT]`, `[likely cut]`). A constant cited with no value is a hedge: assign one, or mark "pick a default; <test> validates".
   - An UNRESOLVED refactor `[USER DECISION]` gates Stage 1: halt, defer to `/qimpag`. Once ruled, the ruling supersedes the stage body. (→ deep-dives §Step 1 — uncertainty markers.)
   - Never measure or trim a file the plan didn't name; no ad-hoc `condense` (4f's context check still runs). Auto-memory writers drop the delete classes, never measure. Trimming a plan-named file IS the work; another bloated-looking file → a `roadmap.md` NTH, never the pointer. (→ deep-dives §Step 1 — never measure a file.)

2. **Evaluate plan size** — count implementation tasks (exclude docs-only/meta).
   - Never ask whether to defer stages or pre-commit to a stopping boundary: execute straight through in plan order; 4f's wrap-up stops at the most recent clean boundary (compiles, tests pass, nothing half-wired). Announce the shape once. (→ deep-dives §Step 2 — never ask to defer.) (→ deep-dives §Step 2 — one rule, any task count.)
   - At that stop, or a budget-cap abort mid-stage, contribute remaining tasks + the sentinel to §project_state.

3. **Execute tasks** — in plan order.
   - Execute HERE, never recon-and-defer (unless the launch prompt literally contains the word "eyeball"): bounded grep + narrow window, then edit. The legitimate stops are exactly five: (1) a 4f wrap-up with committed code; (2) a step-1 gate; (3) the plan-authoring pass; (4) a 4b ownership escalation; (5) same-issue-twice (steps 5/7). Otherwise zero committed file edits is a defect. (→ deep-dives §Step 3 — the five legitimate stops.)
   - The dispatch unit is the stage, triaged once against the gate below (state the choice). A delegated dispatch is ONE committable slice (`Stage N.M`); if it needs whole-stage context, brief "finish slice 1, return a delta-handoff" and re-feed that to a fresh executor (a design-only subagent's handoff is valid). Task-level dispatch survives only as clause (b).
   - Stay where you were launched: never a git worktree, and never `cd` or create/switch branches; subagents work on the current tree. (→ deep-dives §Step 3 — stay where you were launched.)
   - Delegation gate (the READ is the cost, not the edit): delegate recon+edit when ≥1 holds:
      (a) ≥2 unheld large files (≥~800 lines each) or ONE big throwaway acquisition;
      (b) parallel, genuinely independent siblings (disjoint files);
      (c) review/verification wanting independent context;
      (d) recon informing plan-WRITING: only an `Explore` brief enters the parent;
      (e) past the 4f zone AND the task opens fresh territory.
      Inline recon is right in ONLY three cases: (i) the file was Read this session; (ii) bounded pick-and-test (§Rules); (iii) a short file (<~300 lines); a 300–800-line file edits inline via Grep + windows, never a full Read. Gate (a) outranks all three; count large unheld READS, not files to edit. (→ deep-dives §Step 3 — delegate only when it pays.)
   - Parallelize only adjacent tasks independent without reading code (different dirs, or the plan says parallel). Serialize otherwise; after parallel work, run `subagent-dispatch.md` §Parallelization discipline.
   - Research-style plans (no code) → deep-dives §Step 3 — research-style plans.
   - Delegate brief: implement Stage N from [plan]; self-verify with targeted tests + type-checker + every cheap lint the gate command chains, and name the commands in the brief; do NOT commit; touch only focus files (+ related imports/tests); return AS YOUR FINAL MESSAGE, after the self-verify: test command + summary line (no log, no diff), ALL files touched, issues. Scope comes from `git status --short` + that files-touched list. A direct stage must self-verify the same way.
      Pre-resolve, then bound: pass each command/probe/URL verbatim, resolved before dispatch; on failure the subagent reports and stops. Commands run as `… 2>&1 | tail -20`; re-run only the failing file. ⛔ Never chain `&& git commit` after a `| tail` gate. Verify-only briefs → `subagent-dispatch.md` §Verify-agent briefs.
      Every brief that AUTHORS or CHANGES assertions carries this clause verbatim (verify-only briefs omit it):
      *"Any falsifier/grep/confirmer you author must be ABLE to fail (a confirmer likewise to ESTABLISH) — run it file-wide, exclude comment lines, never ship one vacuous by construction (a TS symbol in `.sql`) or indicting its own docblock. This binds TEST ASSERTIONS too: a new/changed assertion owes a red demo — mutate the exact line it guards, confirm the failure, then RESTORE it by re-typing (never `git checkout -- <file>` — it destroys the uncommitted work) — before calling the stage verified. A red demo lives in the WORKING TREE only: never commit the mutated state (a broken SHA on main = bisect landmine); record the failing output in the commit message."*

4. **After each task** — the orchestrator scope-checks and commits; heavy verify batches at the stage boundary (step 6):
   a. Git recon per CLAUDE.md §Efficiency (`git status --short`).
   b. Check changed files (status + the files-touched list) against expected scope; revert out-of-scope files only if you touched them (an untouched one may be a sibling session's: leave it); unsure → ask. `<repo>/.claude/memory/` is always in scope. Dispatched work whose report didn't name the behavior its tests asserted: skim `git diff` of the focus files. Direct edits skip this.
   c. Per task, do NOT re-run the suite: trust the self-verify. A rejected pre-commit hook is a red gate: fix the cause, never `--no-verify`. The full suite + repo-wide type-check run ONCE at the stage boundary (step 6).
      Prose about a number (docblock table, plan finding, commit-message measurement) gets a Haiku `general-purpose` claim-check before committing, holding ONLY the probe's raw output and the prose: does every sentence name the exact quantity computed (arm, denominator, window), and can each cited guard fail? Fix, then commit. (→ deep-dives §Step 4 — the measured-claim check.)
   d. Commit, listing the completed task. Cloud session (`[ "${CLAUDE_CODE_REMOTE:-}" = true ]`): `git push -q -u origin HEAD` after every commit. (→ deep-dives §Cloud session — push and foreground.) No `project_state.md` write per task: the commit log is the per-task record. A memory burst ends in its own `git commit -m "chore(memory): …" -- .claude/memory` (pushed in the cloud; an unlinked project commits nothing).
   e. Mark the task done only after the commit succeeds.
   f. **Wrap-up check**, after every commit: wrap up on a context-budget warning (200k+) or a stage boundary reached past ~45 turns. The first warning overrides any "run all write steps" answer: say in one line what is in flight vs deferred; a further ship or owed item becomes a project_state line, never started; review fixes go to a subagent. A boundary past ~45 turns IS a session boundary: commit, don't start the next stage. Wrapping up = write the remaining rungs plus the rulings already made into the plan doc, contribute remaining tasks to the §project_state burst, jump to step 6. Resume re-runs from Step 1, idempotent. (→ deep-dives §Step 4f — the ~45-turn session boundary.)
   g. Brownfield repos: a commit fixing or working around third-party code adds a bullet (change, fork commit/file, upstream file) to `docs/upstream-pr-candidates.md` under `## <owner>/<repo>`. Delete the bullet when its PR opens upstream (URL in that commit); briefs on such repos carry this clause.

5. **Failed task** — direct edit: fix inline. Dispatched subagent errors: dispatch a fresh fix subagent with the error details. Either path failing twice on the same issue → ask user.

6. **Final review** — run the repo's full suite + type-checker (the batch deferred from 4c) in the orchestrator as background Bash piped through `tail -15`, never inside a verify subagent. Read the command from `CLAUDE.md` (`make test-bats` in dotfiles; `pytest tests/ -q` + `pyright` for Python); no type-checker → skip that half; never invent a gate. Then a fresh `code-reviewer` subagent (never inline review) over `BASE_SHA..HEAD_SHA`.
   - Brief: the plan path + 3–5 concrete verification targets (risky seams/invariants); never paste the diff. `code-reviewer` not registered → don't silently degrade → deep-dives §Step 6 — code-reviewer fallback.
   - Plan-scheduled review wins: a wrap-up before the plan's own final review skips this one; record deferral + range in project_state, and re-measure the range to the plan's own commits before dispatch → deep-dives §Step 6 — deferred plan-scheduled review.
   - End the turn on the dispatch: a ≤2-line status, no recap while review runs.

7. **Fix review issues** — auto-fix Critical/Important via fix subagent(s) immediately, then re-verify; a fix failing twice → ask.
   - The stage is done once review fixes are committed and re-verified; only then contribute "Stage N complete" to project_state (the in-flight resume payload: deleted, not extended, once the next stage lands). Only Nice-to-have findings → done; drop them unless the user asked or it is a defect class known to rot (fix it, grep file-wide); the report and commit message are their record. (→ deep-dives §Step 7 — nice-to-have findings drop.)
   - Continuation sentinel (before Step 8): automatable stages remain → append it per §project_state. Only user-decision work left → no sentinel; write "chain not re-armed — USER DECISION owed on X" into Next-action.

8. **Finish the branch.**
   - **8a. Archive gate**, before the status block on every finishing turn: is the plan still LIVE? Not when every stage is on `main` with only a user-owed confirm left, or when it closed without shipping (refuted, abandoned). Then, same turn: flip `Status:` (`✅ SHIPPED` / `CLOSED WITHOUT SHIPPING`), `git mv` it to `docs/plans/archive/` (pathspec BOTH halves of the rename), move leftover user confirms to roadmap `§OWED[USER]`; per the project's plan-hygiene rule. Archiving is never a question, an offer, or a `Needs you:` or `project_state.md` line; at most one tier-3 clause. An archived plan stops being the Next-action target: repoint, or "no open work". (→ deep-dives §Step 8 — archiving is mechanical.)
   - **8b. Status block**: one block, never a per-task re-narration. Tier 1: a bold TL;DR sentence. Tier 2 `Needs you:`: ≤3 `<Verb> <object>` imperatives actionable TODAY, usually only the push. Tier 3: ≤3 bullets, one per theme. Non-push `Needs you:` lines are mirrored into memory the same turn. (→ deep-dives §Step 8b — the two tier admission tests.)
   - Integration branch (`main`/`dev`/`develop`, or CLAUDE.md-flagged): skip `finishing-a-development-branch`; report branch, commits ahead of `origin/<branch>`, tests (`discard` next turn discards). On a disposable topic branch (`feat/*`), invoke it. Outside the cloud, the push is a tier-2 `Push <branch> from the host`, never mirrored.
   - Cloud session (`[ "${CLAUDE_CODE_REMOTE:-}" = true ]`): the push is YOURS, never a `Needs you:` line. From the session branch: `git fetch origin main && git merge --no-edit origin/main` (never rebase), re-run the step-6 suite unless it fast-forwarded, then `git push origin HEAD:main` (or the CLAUDE.md-flagged integration branch). Rejected: fetch, merge and push once more; a conflict or a second rejection leaves `main` alone and emits `Needs you: Merge <session-branch> into main (conflict in <file>)`. ⛔ Never `--force` or `--no-verify`: a hook-rejected push is a red gate. This directive IS the explicit permission the launch prompt's "never push to another branch" clause asks for. Tier 3 reports `pushed <sha> → origin/main`; no tier-2 push line.
   - Prune fully-merged branches (`git merge-base --is-ancestor <branch> <integration>`) with `git branch -d`, never a permanent dev branch. Delete the remote (`git push origin --delete <branch>`) only where push works (the host, not a devcontainer); else list stale remotes.
   - Continue to step 9 in the same response.

9. **Retrospective — capture-gated, budget-deferred.** Run `/retro` only for a capture item (durable gotcha, user correction, superseded doc claim) whose class isn't recorded: grep its destination first. None → print `retro skipped — no capture items`; zero is normal.
   - Never run it past the 4f zone (200k+): put a ≤1-line `retro owed: <items>` in "Next action" and end. Admit only an item already one sentence naming its destination doc; else drop it, never park it. Better: write it home now, no marker. (→ deep-dives §Step 9 — the retro marker's admission test.)
   - In budget with items: invoke it in the same turn at the main conversation level, NOT as a subagent. Don't narrate 7→8→9.

## project_state

`project_state.md` at `~/.claude/projects/<cwd-slug>/memory/` is impag's live pointer, read by `impag-chain` to re-fire; model → `memory-system.md` §Rolling state. Memory writes are silent: never narrate them.

- One `Write` per turn: steps 1, 2, 4f, 7, 8 and 9 contribute lines; it fires at the last contributing step of the turn.
- Admission test: open or owed, the next session is wrong without it, and no cheaper source has it. ≤200 chars per item, no evidence or rationale; a paragraph belongs in a doc. (→ deep-dives §project_state — the admission test's exclusion lists.)
- The test re-applies on carry-forward: drop the delete classes from old lines, header prose included. (→ deep-dives §project_state — why the admission test re-applies on carry-forward.)
- Holds only the "Next action" pointer, chain/sentinel state and active-task essentials; never a "SHIPPED X" log (the in-flight stage's completed list excepted). Menus, gated work and OWED → roadmap; evidence → the plan doc.
- Re-read it right before the Write; on a modified-since-read trip, merge, never overwrite a sibling's burst. One full-body `Write`, never Edit-appends.
- Emit one in-flight "Next action" (other ▶ work → roadmap), remaining tasks as `plan/spec §N` pointers, the sentinel when chaining. Rewrite stale pointer prose.
- Live claims carry their falsifier: reconcile only what you advance plus any falsifier already in hand; deletions still sweep the whole file, and step 1's resume read is the deep sweep. (→ deep-dives §project_state — full mechanics.)
- Terminal write — pointer-only: plan complete, nothing armed or automatable → only the "Next action" line (user-owed items, or "no open work") plus the roadmap pointer.

**Continuation sentinel.** To chain a fresh session, append this verbatim sentinel on its own line, a machine-read contract with `impag-chain`. Re-emit it on every stage that should chain forward; Next-action prose is no substitute.

```
<!-- impag-chain-next-stage -->
```

"Chain ARMED" is a CLAIM: grep it in the same burst, with the driver's own path and regex:

```
slug="${PWD//[^a-zA-Z0-9]/-}"   # the harness's replace(/[^a-zA-Z0-9]/g,"-") — a `claude --worktree` cwd has a dot, `claude_skills` an underscore
mem="$HOME/.claude/projects/${slug}/memory/project_state.md"
grep -qE '^<!-- impag-chain-next-stage(: [1-9][0-9]*)? -->$' "$mem"
```

Match the legacy `: N` suffix, but always EMIT the no-suffix form above.

## Rules

- Sub-agent model routing: pins live in `.claude/agents/*.md` frontmatter, never here; subagents run at their pinned defaults. Read-only `Explore`/search fan-out is pinned Haiku/`low`, the only downshift tier: push every bounded find/grep/locate there. Set `model:` only when it must differ (it overrides the pin, keeps the pinned effort); `sonnet` stays retired.
- Thin orchestrator: past the 4f zone with stages still queued, the orchestrator holds NO file bodies; it dispatches, scope-gates from the files-touched report, commits and gates, and subagents do all reading and editing. Below that, direct-edit-default still wins. (→ deep-dives §Rules — thin orchestrator + late-session recon.)
- After a background dispatch (e.g. the step-6 code-reviewer), end the turn and wait for its notification: no polling, no status pokes. A task is done only when the harness's notification arrives; never author one.
- Cloud (`[ "${CLAUDE_CODE_REMOTE:-}" = true ]`): EXECUTOR dispatches run FOREGROUND (`run_in_background: false`), so 4d commits and pushes before the turn ends; the reviewer stays background. If the launcher's Stop hook still fires, answer one line ("in-flight subagent work, not yet self-verified; commits when its report arrives") and stop again. Never commit to satisfy it. (→ deep-dives §Cloud session — push and foreground.)
- A subagent that died on a transient API error (529, transport) is resumed, not relaunched: `SendMessage` its id with "continue — the error was transient". One over ~130k `<subagent_tokens>` → a fresh agent with a self-contained brief (predecessor's commit, files, ruling).
- A late human-input pause is a stop, not a wait: past the 4f zone, write the question into "Next action" if it gates the armed item (else roadmap `§OWED[USER]`), leave the chain un-armed, end the turn. Ask inline only when the user spoke this turn and the answer unblocks a task in flight. (→ deep-dives §Rules — late human-input pause.)
- Late-session recon whose only deliverable is a roadmap note or a pass/fail verdict → `Explore` or defer. A plan-contract (qimpag questions, addendum anchors) needs a brief, not the subsystem. Gauge budget BEFORE deep-reading a next stage's files; prefer chaining. Reconned anyway → bank the design into the plan doc or its addendum, never `project_state`. (→ deep-dives §Step 3 — execution recon needs the same bound.)
- Pick-and-test recon: confirm a plan-cited symbol with one grep plus a ~20–40-line window, then edit; tests adjudicate, not a multi-file derivation. An underdetermined value → pick the plan's default and let the test decide, but sanity-bound a one-sided-verifiable constant. A constant cited with no value is a plan gap: surface it at step 1.
- A per-stage plan file only when a session NOT executing the stage would re-read its plan; then its own `docs/plans/` file, never appended to a growing design doc (iteration specs → `~/.claude/references/iterative-spec-loop.md` §Doc mechanics). (→ deep-dives §Rules — per-stage plan files.)
- Numeric ecosystem constants in a plan (cache TTLs, autocompact thresholds, timeouts, retention counts) → web-verify before shipping (`~/.claude/references/pre-ship-sweeps.md` §External-ecosystem constants).
