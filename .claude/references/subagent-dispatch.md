# Sub-agent dispatch

## Delegate by output size and reducibility, never by command name

**Delegation moves *content* out of the parent. It does not move the *prefix*.** An `Agent(...)` call is itself a parent turn: it re-bills the full context and regenerates the turn's thinking exactly as an inline `Bash`/`Read` would. On top of that you pay the sub-agent's from-zero startup (system prompt + `CLAUDE.md` + tool defs, ~15k tokens, no share of the parent's cache), the parent-priced output tokens that write its brief, and the report it returns — which lands in the parent context and is re-billed on every subsequent turn anyway.

So **delegation never saves a round-trip.** It is purely a content-size trade, and it pays only when:

```
(raw_output − report_size) × 0.1 × remaining_turns  >  subagent_startup + brief_cost
```

**Threshold.** Under ~1k tokens of raw output, or whenever the parent needs the bytes themselves (the `git status --short` file list it is about to scope-gate against), run it inline. Delegate when the output is several thousand tokens **and** collapses to a verdict the parent can act on without ever seeing the raw bytes.

Worked, from the 2026-07-10 private-app chain:
- `git status --short` emitted 114 chars ≈ 30 tokens. Inline, that costs ~190 billed tokens over 50 remaining turns (`1.25×30` to cache, `0.1×30×50` to re-read) ≈ **$0.001**. Delegated, the parent still spends ~300 *output* tokens writing the brief (output is the 5×-priced line) and the report re-enters context anyway, plus ~15k of Haiku prefix from zero: ≈ **$0.04, roughly 40× worse — and you still pay the parent round-trip.** Delegating small-output recon is strictly a loss.
- One bare `git diff` emitted 7,804 chars ≈ 2,000 tokens; keeping it out over 58 remaining turns saves ~11.6k tokens — which roughly *cancels* the sub-agent's cost. A wash, and the wrong question: the rule (`CLAUDE.md` git-recon bullet, impag step 4a) says don't run it at all. **Eliminating overproduction beats optimizing transportation** — check whether the call is needed before deciding where to run it.
- Five `git show HEAD:<blob>` extractions feeding python diffs to answer "did the regen still match" — thousands of tokens of JSON in, one line of verdict out. **This is the shape that pays**: one dispatch, one sentence back. Same shape as `git show BASE..HEAD` inside the step-6 `code-reviewer`, and as a history audit ("which of these 40 commits touched X").

## Never delegate mutating git; read-only git is fine

Verified 2026-07-10: **hooks DO fire for sub-agent tool calls** — a Haiku `Explore` agent's `wget … | sh` was blocked by `destructive-bash-gate` before it executed. Delegating therefore forfeits no hook protection. The problem is that **no hook covers git in the first place**: `destructive-bash-gate` handles `rm` / downloader-piped-to-shell / `.ssh` writes only, and `settings.json` carries zero git entries in `deny`, `ask`, or `allow`. `git reset`, `git checkout --`, `git stash`, and `git push` have no backstop anywhere.

Reads (`status`, `log`, `show`, `diff`, `merge-base`) are safe to delegate on the size rule above. Mutations are not, for reasons that survive the hook finding:

1. **No backstop** (above). True in the parent too — but the parent has your judgment and the user's visibility in the loop.
2. **It breaks the scope gate.** impag step 4 deliberately keeps commits in the orchestrator and tells dispatched sub-agents "do NOT commit", so one agent owns working-tree state and can check `git status --short` against expected scope. A committing sub-agent makes that check meaningless.
3. **Concurrency.** Parallel sub-agents share one worktree's `.git/index`; two `git add`/`commit` sequences race on `index.lock` and cross-contaminate commits. That is what `isolation: "worktree"` exists for.
4. **Model/effort mismatch.** `Explore` pins to Haiku at `low` effort. Choosing paths for `git checkout --` is a judgment call, and the Iron Rule "never `git reset --hard` on a push failure" does not survive delegation to the cheapest model at the lowest effort.

## Parallelization discipline

Only parallelize sub-agents when they modify independent files. After sub-agents complete, verify cross-file consistency (dep lists, imports, exports that reference changed code) — sub-agents see their target file but miss references elsewhere in the same file or in sibling files.

**A repo-wide gate run INSIDE a parallel sibling proves nothing, and its green is not evidence you may relay.** Each sibling runs the suite against a tree its peers are still mutating, so every one can report green over a state that never existed whole and is gone before the last one commits. No sibling's run is authoritative — and the failure is silent, because N green reports read as N confirmations rather than N mutually-invalidated snapshots. Instruct parallel siblings to run only *targeted* tests over their own focus files, and run the repo-wide gate **once, in the orchestrator, after the last sibling returns**. Same bound on any whole-tree measurement (a file count, a repo-wide grep census): take it after the barrier, never inside an arm.

## Plan subagent can't Write

The `Plan` subagent's tool set excludes `Write`/`Edit`/`NotebookEdit`. When using it to produce a design doc, either (a) tell it to return the full doc content verbatim in its final message so the parent session writes it to disk, or (b) stub the file path first and have it report the intended content by section. Don't instruct it to "save the plan" — it will produce the doc and then note it couldn't write, costing a round-trip.

## Background bash for long-runners

When a command will plausibly exceed the 2-minute Bash default (full test suites, builds, large scrapes, container rebuilds), set `run_in_background: true` and poll via `BashOutput(shell_id)` / `KillShell(shell_id)`. The hard ceiling is 10 min — anything past it returns truncated output and wastes the streamed context on retry. Short overruns can use `timeout: 600000` inline; anything reliably >5 min should run backgrounded from the first call.

## Research subagents for codebase spelunking

For broad exploration that would take ≥3 Glob/Grep rounds, dispatch `Agent(subagent_type="Explore")` instead of polling the main context across rounds. Only the final consolidated summary comes back; intermediate searches never pollute main-context tokens. Use for "where is X handled" / "what's the architecture of Y" / "enumerate all call sites of Z". Pick `Plan` for design questions (read-only), `general-purpose` when you need tool-write access mid-investigation.

## Worktree for multi-file features

When a task will touch ≥4 files under the same package, spin up a git worktree via `superpowers:using-git-worktrees` before the first edit. Keeps the main tree pristine for diff/compare and isolates WIP from concurrent sessions. Pairs with the CWD Iron Rule — still use absolute paths, don't `cd` into the worktree root. One-off edits and single-file fixes don't need it.

## Deep pattern-extraction from a known large file, even solo

Distinct from "broad exploration" above: when a task needs to precisely mirror an existing pattern in one
already-large file (≥800 lines) — exact function body, data shape, line-anchored algorithm — to write new
interoperating code, the targeted `Read` calls to extract that pattern cost heavily even though file *count*
is 1 and you already know the target lines via `grep`. A file-count-based delegation gate (e.g. "4+ files ⇒
direct") doesn't catch this: it's read-depth-into-one-file, not edit-file-count, that burns the budget. In a
budget-constrained/chained session, dispatch a subagent to extract the pattern (exact snippets + line
numbers + a compact written contract) rather than reading it inline — cheaper than the orchestrator paying
full file-context cost twice (once to understand, again implicitly held for the edit). Symptom seen twice
in the same private-app session chain: qimpag hit the ~130k wrap-up hook on inline recon of a 1499-line
Python file before any edit landed, both times.

## Background agents auto-notify — don't poll

After dispatching a background agent (e.g. a code-reviewer), the harness re-invokes you with its result on completion. Do NOT schedule a `ScheduleWakeup`/fallback wakeup to poll for it, and do NOT `SendMessage`-poke a still-running agent for status — just end the turn and wait for the notification. Only message a running agent if the user explicitly asks, or to redirect its work (not to check progress).

**A `SendMessage` to a COMPLETED agent RESUMES it, and it reads the message as "continue the task."** A note intended only as a budget guard restarted a finished agent, which re-entered the stage while a freshly-launched replacement was already working it — two writers, one shared tree. Send a budget guard BEFORE the work starts; once an agent has completed, either accept that messaging it hands the task back (and do not relaunch), or launch a replacement and never message the original.

**Stall exception:** an agent that spawned its OWN background Bash can notify-complete while still owing its final report ("I'll finalize when its notification lands") and then never re-fire. Diagnose with `ps` (no matching processes) + the agent output file's mtime (minutes-stale); recover with one `SendMessage` telling it the child already exited — finalize now (verified 2026-07-16). That's a stalled-agent rescue, not status-polling.

## Code-review dispatch — evidence

Benched 2026-07-09: the bundled `/code-review` bought no extra recall over a fresh `code-reviewer` sub-agent at ~14× the tokens — hence its `user-invocable-only` gate in `settings.json`; typed bare in an xhigh session it silently escalates to a background workflow (one finder per angle + an independent verifier per candidate). Defect-class triage example, 2026-07-18: a Nice-to-have "docblock overstates the shape" finding, treated as a class and grepped file-wide, surfaced three more false docblocks in the same file.

## Secrets: brief the guard, or the subagent echoes the value

A diagnostic subagent printed a keyed env var's VALUE into its transcript (2026-08-16, `WEBSTAT_API_KEY` — rotation owed). **Every brief touching env/config carries: report a secret's NAME and set/unset only — no `echo $VAR`, no `env`/`printenv` dump, no pasted `.env` line.**

## A subagent's report is EVIDENCE, never a verification you performed

Two failure modes, both 2026-08-04, both invisible in the transcript because the sentence reads the same either way.

**Laundering.** A brief's assertion ("no other call site does X") was written into a plan as "verified by file-wide grep" — no such grep was ever run. A subagent's claim inherits the subagent's uncertainty; restating it in the first person strips exactly the provenance a later reader would use to re-check it. **Rule: attribute or re-run.** Write "the recon agent reported X" and keep it a report, or run the grep yourself and quote the command. Never a first-person verification verb over a claim you received.

**Relaying a false premise.** A review finding handed verbatim to a fix agent carried a premise that was wrong; the fix agent, having no way to see past the brief, implemented against it. **Rule: before relaying a finding, check its premise against the tree** (does the cited symbol exist at HEAD? does the flow actually run that way?) — a fix subagent trusts the brief absolutely, so the relay point is the last place the premise can be caught.

**An ESCALATION is a claim too — the costliest one, because it ends the session.** An executor returned "this is a design fork, not a re-pin — I stopped rather than pick"; it was not a fork at all (two call sites passed identical inputs; two test fixtures had broken their own isolation). One bounded verification pass turned a session-ending user decision into a fixture fix. **Rule: an agent saying "you must rule on this" has asserted a mechanism — verify that mechanism before honouring the stop.**

## A self-verify scoped to the touched test file is not a suite pass

2026-08-20: an executor changed a core function, self-verified by running only the test file it had edited, and reported green. The full suite was red in **five** other files that exercised the same function through different callers — none of them in the stage's focus set, so nothing in the brief pointed at them. The report was honest and the orchestrator had no signal.

**Rule: the self-verify command in a brief must be scoped to the CHANGE'S BLAST RADIUS, not to the files edited.** When a stage touches a shared/core symbol, name the full-suite command in the brief (`npm run check` here), not the targeted file — the targeted-test shortcut is only correct for a leaf change whose symbol has one caller. When in doubt, the orchestrator's step-6 batch is the backstop, but it fires a stage late: a red suite discovered there costs a fix dispatch plus a re-verify that a one-line brief change would have prevented.

## Brief the stage's OWN committable boundary, not a blanket "full gate green"

2026-08-20: an executor was briefed with a blanket "full gate green before you return". Its stage's committable boundary was legitimately split across two commits (the second one regenerated goldens the first moved), so at the end of slice 1 the gate was red **by design** — and the executor reported a blocker rather than a boundary. A session-ending stop bought by an imprecise sentence.

**Rule: quote the plan stage's OWN `Committable boundary:` line into the brief, verbatim, as the definition of done — plus what is allowed to be red at it — then name the self-verify command underneath it.** "Stage N is done when X compiles and `<targeted command>` passes; the vintage/snapshot pins are EXPECTED red and are Stage N+1" is a brief the executor can finish against. Keep the full gate as the orchestrator's step-6 batch, where it belongs.

## Verify-agent briefs

2026-09-11 (private-app leg-chart Stage 3): one verify agent was briefed with the full gate + an open-ended prod-drift hunt + a browser check. Bundled, each item's output is re-billed on every later call of the others.

**Rule: one heavy-output item per dispatch.** Split a gate, a prod measurement and a browser check into separate dispatches — the gate itself runs in the orchestrator as `tail`-bounded background Bash (impag step 6). Hand each the exact command, pre-resolved in the parent. Never `Read` screenshots: assert in the script, report paths. Grep support scripts for the port/URL, never full-read them. Don't re-read diffs a parallel code review already covers. Omit the red-demo clause unless the brief authors assertions.

## Size ONE dispatch to ONE committable slice — a multi-slice brief has no ceiling

2026-09-08, private-app business-day feed-lag qimpag: one executor was briefed to carry **four**
committable slices in a single dispatch. It burned **38M cache-read across 212 turns** — the
sub-agent's own context grows with every file it opens, and each later turn re-reads the whole
accumulated prefix, so a brief spanning N slices pays the sum of N prefixes, not N times a small one.
Two dispatches later in the same session, each scoped to a **single finding with its target files
named in the brief**, came in at **~104k and ~108k** — three orders of magnitude apart, doing
comparable per-slice work.

The failure is not the executor's. A brief with four boundaries in it gives the agent no point at
which to stop and hand back, so it keeps the whole arc resident: slice 1's exploration is still in
context while slice 4 is being edited, and nothing ever drops out.

**Rule: one dispatch = one committable boundary, with the files it may touch named in the brief.**
The `Committable boundary:` line (previous section) is the *definition of done*; this section says it
is also the *dispatch unit*. If a plan stage has four boundaries, that is four dispatches — the
orchestrator re-picks after each, which is the point. Naming the target files up front is what keeps
the executor's exploration bounded; a brief that says "find where X lives" pays for the search on
every subsequent turn of that agent's life.

Corollary for the orchestrator: cost per dispatch is **superlinear in the brief's scope**, so
"batching the slices to save startup" is exactly backwards — the ~15k startup you avoid is dwarfed by
the prefix you fail to drop.

## A recon subagent's STRUCTURAL claim is a claim

A brief that reports "X is defined at Y" or "the six ids carry Z" is evidence, not verification —
and when that structure CARRIES A RULING (an `AskUserQuestion` option, a delete/keep decision),
re-grep the anchor yourself before offering it. A truncated `| head` in the brief's own recon is
enough to turn six ids into four and hand the user a false-premise round.
