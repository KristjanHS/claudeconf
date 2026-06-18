# Sub-agent dispatch

## Parallelization discipline

Only parallelize sub-agents when they modify independent files. After sub-agents complete, verify cross-file consistency (dep lists, imports, exports that reference changed code) — sub-agents see their target file but miss references elsewhere in the same file or in sibling files.

## Plan subagent can't Write

The `Plan` subagent's tool set excludes `Write`/`Edit`/`NotebookEdit`. When using it to produce a design doc, either (a) tell it to return the full doc content verbatim in its final message so the parent session writes it to disk, or (b) stub the file path first and have it report the intended content by section. Don't instruct it to "save the plan" — it will produce the doc and then note it couldn't write, costing a round-trip.

## Background bash for long-runners

When a command will plausibly exceed the 2-minute Bash default (full test suites, builds, large scrapes, container rebuilds), set `run_in_background: true` and poll via `BashOutput(shell_id)` / `KillShell(shell_id)`. The hard ceiling is 10 min — anything past it returns truncated output and wastes the streamed context on retry. Short overruns can use `timeout: 600000` inline; anything reliably >5 min should run backgrounded from the first call.

## Research subagents for codebase spelunking

For broad exploration that would take ≥3 Glob/Grep rounds, dispatch `Agent(subagent_type="Explore")` instead of polling the main context across rounds. Only the final consolidated summary comes back; intermediate searches never pollute main-context tokens. Use for "where is X handled" / "what's the architecture of Y" / "enumerate all call sites of Z". Pick `Plan` for design questions (read-only), `general-purpose` when you need tool-write access mid-investigation.

## Worktree for multi-file features

When a task will touch ≥4 files under the same package, spin up a git worktree before the first edit. Keeps the main tree pristine for diff/compare and isolates WIP from concurrent sessions. Pairs with the CWD Iron Rule — still use absolute paths, don't `cd` into the worktree root. One-off edits and single-file fixes don't need it.
